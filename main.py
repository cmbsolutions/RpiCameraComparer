import sys
import re
import cv2
import numpy
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt, QUrl
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QDialog
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QSoundEffect
from qglpicamera2_wrapper import QGlPicamera2
from mainWindow import Ui_MainWindow
from functools import partial
from libcamera import controls
from capture_thread import CaptureThread
from run_ocr_thread import RunOCRThread
from run_ai_thread import RunAIThread
from run_image_thread import RunImageThread
from PIL import Image
from segment_digits import ai_helper
import tensorflow as tf
from enumerations import EngineType
from pathlib import Path
from gpiozero import Button, OutputDevice
from settings import SettingsDialog
import subprocess

# ───── Configuration ─────
TRIGGER_PIN = 4
OUTPUT_PIN = 22
PULSE_TIME = 0.5  # seconds

BASE = Path(__file__).parent.resolve()
IMG_DIR = BASE / "Captures"
IMG_DIR.mkdir(parents=True, exist_ok=True)


# ----- Main class -----
class MainWindow(QtWidgets.QMainWindow):
    gpio_triggered = Signal()

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.Frame_Error.hide()
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        self._lens_pos = [float(settings.value(f"lensposition/{i}", 0.0)) for i in (0, 1)]
        self._roivals = [settings.value(f"roi/{i}", None) for i in (0, 1)]
        self._focus_supported = {}
        self._frame_array = {}
        self.collecting = False
        self._capture_thread = {}
        self._ocr_thread = {}
        self._ai_thread = {}
        self._image_thread = {}
        self._capturing = False
        self._captured_digits = {}
        self._captured = 0
        self._halt = False
        self._engine = settings.value("engine", EngineType.PYTESSERACT_OCR.value)
        self._save_images = settings.value("saveimages", True, type=bool)
        self._is_locked = settings.value("is_locked", False, type=bool)
        self._password = settings.value("password", "changeme", type=str)
        self._audio = settings.value("audio", True, type=bool)
        self._fullscreen = settings.value("fullscreen", True, type=bool)
        
        self._alarmsound = QSoundEffect()
        self._alarmsound.setSource(QUrl.fromLocalFile("alarm.wav"))
        self._alarmsound.setLoopCount(1)
        self._alarmsound.setVolume(1)

         # This is the AI model
        self._model = tf.keras.models.load_model("ai_model/digit_cnn_model6.keras")
        
        self.gpio_triggered.connect(self.onGpioTriggered)

        # Setup GPIO
        self.gpiotrigger = Button(TRIGGER_PIN, pull_up=True, bounce_time=0.05)
        self.gpiooutput = OutputDevice(OUTPUT_PIN)
        self.gpiooutput.on()
        self.gpiotrigger.when_pressed = self.handle_gpiotrigger

        if self._fullscreen:
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.showFullScreen()

        QtCore.QTimer.singleShot(100, self._insert_cameras)
    

    def _insert_cameras(self):
        # get the placeholders and replace them with the camerafeeds
        for idx in (0, 1):
            grid = getattr(self.ui, f"Cam{idx}Grid")
            placeholder = getattr(self.ui, f"Cam{idx}Source")

            placeholderIndex = grid.indexOf(placeholder)
            row, col, rowspan, colspan = grid.getItemPosition(placeholderIndex)

            grid.removeWidget(placeholder)
            placeholder.deleteLater()

            parent = placeholder.parentWidget()

            # This is not the default QGlPicamera2 class, it is an overridden one that adds selecting regions
            camw = QGlPicamera2(parent=parent, width=640, height=480, keep_ar=True, camid=idx)
            camw.setObjectName(placeholder.objectName())

            grid.addWidget(camw, row, col, rowspan, colspan)
            setattr(self.ui, placeholder.objectName(), camw)

            camw.show()
            camw.picam2.start(show_preview=True)  
 
            # Check if there is AfMode available on the camera
            available = camw.picam2.camera_controls.keys()

            if "AfMode" in available and "LensPosition" in available:
                self._focus_supported[idx] = True
                camw.picam2.set_controls({"AfMode": controls.AfModeEnum.Manual})
                mn, mx, df = camw.picam2.camera_controls["LensPosition"]
                
                if self._lens_pos[idx] != df:
                    getattr(self.ui, f"Cam{idx}Source").picam2.set_controls({"LensPosition": self._lens_pos[idx]})
                    df = self._lens_pos[idx]
                else:
                    self._lens_pos[idx] = df

                getattr(self.ui, f"Cam{idx}Slider").setMinimum(int(mn*10))
                getattr(self.ui, f"Cam{idx}Slider").setMaximum(int(mx*10))
                getattr(self.ui, f"Cam{idx}Slider").setValue(int(df*10))
            else:
                self._focus_supported[idx] = False
                self._lens_pos[idx] = None

                getattr(self.ui, f"Cam{idx}FocusPlus").setEnabled(False)
                getattr(self.ui, f"Cam{idx}FocusMinus").setEnabled(False)

        self.LoadCamRoi()

# ROI stuff
    def ResetCamRoi(self, checked: bool):
        cam_index = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_index}Source")
        widget.set_overlay(None)


    def LoadCamRoi(self):
        for idx in (0, 1):
            # Convert as needed:
            if isinstance(self._roivals[idx], str):
                roi_tuple = tuple(map(int, self._roivals[idx].strip("()").split(",")))
            elif isinstance(self._roivals[idx], (list, tuple)):
                roi_tuple = tuple(int(v) for v in self._roivals[idx])
            else:
                roi_tuple = None
            # Set it on the widget
            if roi_tuple:
                widget = getattr(self.ui, f"Cam{idx}Source")
                widget.set_roi(roi_tuple)


# Camera focus controls
    def CamOnFocusButton(self, checked: bool):
        btn = self.sender()
        name = btn.objectName()

        m = re.match(r"Cam(\d)Focus(Plus|Minus)", name)
        if not m:
            return
        
        cam_idx = int(m.group(1))
        action = m.group(2)

        mn, mx, _ = getattr(self.ui, f"Cam{cam_idx}Source").picam2.camera_controls["LensPosition"]
        delta = 1.0  # choose your step-size
        pos = self._lens_pos[cam_idx] + (delta if action=="Plus" else -delta)
        pos = max(mn, min(mx, pos))    # clamp to [mn, mx]
        self._lens_pos[cam_idx] = pos

        getattr(self.ui, f"Cam{cam_idx}Source").picam2.set_controls({"LensPosition": pos})
        getattr(self.ui, f"Cam{cam_idx}Slider").setValue(int(pos*10))


    def CamOnFocusSlider(self):
        cam_idx = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_idx}Slider")

        pos = self._lens_pos[cam_idx] = widget.value()/10
        self._lens_pos[cam_idx] = pos
        getattr(self.ui, f"Cam{cam_idx}Source").picam2.set_controls({"LensPosition": pos})


 # Capture controls   
    def TestCam(self, checked: bool):
        cam_idx = int(self.sender().objectName()[3])
        self._captured = 0

        widget = getattr(self.ui, f"Cam{cam_idx}Source")

        match self._engine:
            case EngineType.AI_MODEL.value:
                self._ai_thread[cam_idx] = RunAIThread(widget)
                self._ai_thread[cam_idx].ai_captured_result.connect(self.digits_captured)
                self._ai_thread[cam_idx].finished.connect(lambda: self._ai_thread[cam_idx].deleteLater())
                self._ai_thread[cam_idx].start()
            case EngineType.PYTESSERACT_OCR.value:
                self._ocr_thread[cam_idx] = RunOCRThread(widget)
                self._ocr_thread[cam_idx].ocr_captured_result.connect(self.digits_captured)
                self._ocr_thread[cam_idx].finished.connect(lambda: self._ocr_thread[cam_idx].deleteLater())
                self._ocr_thread[cam_idx].start()


# Callback from capture_array from camera
    def handleCaptured(self, frame_array, cam_idx):
        self._cam_idx = cam_idx
        self._frame_array[cam_idx] = frame_array
        roi = getattr(self.ui, f"Cam{cam_idx}Source")._roi

        match self._engine:
            case EngineType.AI_MODEL.value:
                self._ai_thread[cam_idx] = RunAIThread(frame_array, cam_idx, roi, self._model)
                self._ai_thread[cam_idx].ai_captured_result.connect(self.digits_captured)
                self._ai_thread[cam_idx].finished.connect(lambda: self._ai_thread[cam_idx].deleteLater())
                self._ai_thread[cam_idx].start()
            case EngineType.PYTESSERACT_OCR.value:
                self._ocr_thread[cam_idx] = RunOCRThread(frame_array, cam_idx, roi)
                self._ocr_thread[cam_idx].ocr_captured_result.connect(self.digits_captured)
                self._ocr_thread[cam_idx].finished.connect(lambda: self._ocr_thread[cam_idx].deleteLater())
                self._ocr_thread[cam_idx].start()


    def digits_captured(self, rgb, cam_idx, digits):
        if not self._halt:
            getattr(self.ui, f"Cam{cam_idx}CapturedValue").setText(f"CAM{cam_idx}: {digits}")
            self._captured_digits[cam_idx] = digits
            self._captured += 1

        if self._captured >= 2:
            if self._captured_digits[0] != self._captured_digits[1]:
                self.onDigitsNotMatching()
            else:
                getattr(self.ui, "Frame_Error").setStyleSheet("color: green;")
                getattr(self.ui, "Frame_Error").show()

        if self._save_images:
            self._image_thread[cam_idx] = RunImageThread(IMG_DIR, rgb, cam_idx, digits)
            self._image_thread[cam_idx].finished.connect(lambda: self._image_thread[cam_idx].quit())
            self._image_thread[cam_idx].start()


    def onDigitsNotMatching(self):
        self.gpiooutput.off()
        self._halt = True
        getattr(self.ui, "Frame_Error").setStyleSheet("color: red;")
        getattr(self.ui, "Frame_Error").show()
        getattr(self.ui, "ResetError").setEnabled(True)
        self.ui.bTriggerManual.setEnabled(False)
        self.ui.Cam0TestCapture.setEnabled(False)
        self.ui.Cam1TestCapture.setEnabled(False)
        
        if self._audio:
            self._alarmsound.play()


    def handle_gpiotrigger(self):
        self.gpio_triggered.emit()


    def onGpioTriggered(self):
        if self._capturing and not self._halt:
            self._captured = 0

            self.CompareImages()


    def StartCapturing(self):
        if self._capturing:
            self._capturing = False
            getattr(self.ui, "StartCapture").setText("Start capture")
            getattr(self.ui, "StartCapture").setIcon(QIcon(":/main/gtk-media-play-ltr.png"))
        else:
            self._capturing = True
            getattr(self.ui, "StartCapture").setText("Stop capture")
            getattr(self.ui, "StartCapture").setIcon(QIcon(":/main/gtk-media-pause.png"))


    def CompareImages(self):
        for cam_idx in (0, 1):
            widget = getattr(self.ui, f"Cam{cam_idx}Source")

            match self._engine:
                case EngineType.AI_MODEL.value:
                    self._ai_thread[cam_idx] = RunAIThread(widget)
                    self._ai_thread[cam_idx].ai_captured_result.connect(self.digits_captured)
                    self._ai_thread[cam_idx].finished.connect(lambda: self._ai_thread[cam_idx].quit())
                    self._ai_thread[cam_idx].start()
                case EngineType.PYTESSERACT_OCR.value:
                    self._ocr_thread[cam_idx] = RunOCRThread(widget)
                    self._ocr_thread[cam_idx].ocr_captured_result.connect(self.digits_captured)
                    self._ocr_thread[cam_idx].finished.connect(lambda: self._ocr_thread[cam_idx].quit())
                    self._ocr_thread[cam_idx].start()


    def ResetError(self):
        self.gpiooutput.on()
        self._halt = False
        getattr(self.ui, "Frame_Error").hide()
        getattr(self.ui, "ResetError").setEnabled(False)
        self.ui.bTriggerManual.setEnabled(True)
        self.ui.Cam0TestCapture.setEnabled(True)
        self.ui.Cam1TestCapture.setEnabled(True)

    
    def SaveFileDialog(self):
        cam_idx = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

        self._capture_thread[cam_idx] = CaptureThread(widget)
        self._capture_thread[cam_idx].image_captured.connect(self.SaveFileDialogHandler)
        self._capture_thread[cam_idx].finished.connect(lambda: self._capture_thread[cam_idx].deleteLater())
        self._capture_thread[cam_idx].start()


    def SaveFileDialogHandler(self, frame_array, cam_idx):
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image As...",
            dir="",
            filter="PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)",
            options=QFileDialog.Options()
        )
        if filename:
            rgb = frame_array[...,:3].copy()
            img = Image.fromarray(frame_array)
            img.save(f"{filename}.png", format="PNG")


    def ExitApplicationHandler(self):
        self.close()


    def RebootHandler(self):
        if self._is_locked:
            ok = self.ask_for_password(subject="Reboot")
            if ok:
                self.SaveSettings()
                self.gpiooutput.off()
                self.gpiotrigger.close()
                subprocess.run(["sudo", "reboot", "--reboot"])


    def ShutdownHandler(self):
        if self._is_locked:
            ok = self.ask_for_password(subject="Shutdown")
            if ok:
                self.SaveSettings()
                self.gpiooutput.off()
                self.gpiotrigger.close()
                subprocess.run(["sudo", "shutdown", "-h", "now"])


# Settings dialog, and on close
    def SettingsHandler(self):
        if self._is_locked:
            ok = self.ask_for_password(subject="Modify settings")
            if ok:
                settings = SettingsDialog(self)
                settings.settings_changed.connect(self.ReloadSettings)
                result = settings.exec()
        else:
            settings = SettingsDialog(self)
            settings.settings_changed.connect(self.ReloadSettings)
            result = settings.exec()
            

    def ReloadSettings(self):
        settings = QSettings("CMBSolutions", "RpiCameraComparer")

        self._engine = settings.value("engine", EngineType.PYTESSERACT_OCR.value)
        self._save_images = settings.value("saveimages", True)
        self._is_locked = settings.value("is_locked", True)
        self._password = settings.value("password", "RPICameraComparer")
        self._audio = settings.value("audio", True, type=bool)


    def SaveSettings(self):
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        for idx in (0, 1):
            if self._focus_supported[idx]:
                settings.setValue(f"lensposition/{idx}", self._lens_pos[idx])
            else:
                settings.setValue(f"lensposition/{idx}", 0.0)
            roi = getattr(self.ui, f"Cam{idx}Source").GetRoi()
            settings.setValue(f"roi/{idx}", roi)


    def UnlockHandler(self):
        password, ok = QInputDialog.getText(self, "Unlock", "Enter password to unlock:", QLineEdit.Password)
        return ok and (password == self._password)


    def ask_for_password(self, subject="Exit"):
        password, ok = QInputDialog.getText(self, subject, "Please enter the password.", QLineEdit.Password)
        return ok and (password == self._password)
    

    def closeEvent(self, event):
        if self._is_locked:
            ok = self.ask_for_password(subject="Exit Application")
            if not ok:
                event.ignore()
                return
                
        self.SaveSettings()
        super().closeEvent(event)


    def keyPressEvent(self, event):
        if self._is_locked:
            if event.key() in (Qt.Key_Escape, Qt.Key_F4, Qt.Key_Alt + Qt.Key_Tab):
                pass  # ignore
            else:
                super().keyPressEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())