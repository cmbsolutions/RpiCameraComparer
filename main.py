import sys
import re
import cv2
import numpy
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt, QUrl
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox
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
import time
from navicatEncrypt import NavicatCrypto


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

        self._focus_supported = {}
        self._frame_array = {}
        self.collecting = False
        self._capture_thread = {}
        self._ocr_thread = {}
        self._ocr_thread_busy = {}
        self._ai_thread = {}
        self._image_thread = {}
        self._image_thread_busy = {}
        self._capturing = False
        self._captured_digits = {}
        self._captured = 0
        self._halt = False

        self._navicat_crypto = NavicatCrypto()

        # Load settings
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        self._lens_pos = [float(settings.value(f"lensposition/{i}", 0.0)) for i in (0, 1)]
        self._roivals = [settings.value(f"roi/{i}", None) for i in (0, 1)]
        self._engine = settings.value("engine", EngineType.PYTESSERACT_OCR.value)
        self._save_images = settings.value("saveimages", True, type=bool)
        self._is_locked = settings.value("is_locked", False, type=bool)
        self._password = self._navicat_crypto.DecryptString(settings.value("password", "", type=str))
        self._audio = settings.value("audio", True, type=bool)
        self._fullscreen = settings.value("fullscreen", True, type=bool)

        #metrics
        self._speed = 0.0
        self._matchcount = 0
        self._matchcountTotal = settings.value("matchcounttotal", 0, type=int)
        self._errorcount = 0
        self._errorcountTotal = settings.value("errorcounttotal", 0, type=int)
        self._last_time = None
        self.UpdateMetrics()

        #sound component
        self._alarmsound = QSoundEffect()
        self._alarmsound.setSource(QUrl.fromLocalFile("alarm.wav"))
        self._alarmsound.setLoopCount(1)
        self._alarmsound.setVolume(1)

         # This is the AI model, we load it here instead of in the ai thread because it is large and we want to avoid loading it multiple times
        self._model = tf.keras.models.load_model("ai_model/digit_cnn_model7.keras")
        
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
 
            self._ocr_thread_busy[idx] = False
            self._image_thread_busy[idx] = False

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
                    if self._ai_thread_busy[cam_idx]:
                        prev = self._ai_thread.get(cam_idx)
                        if prev and prev.isRunning():
                            if not prev.wait(50):
                                return

                    self._ai_thread_busy[cam_idx] = True
                    t = RunAIThread(widget)
                    t.setParent(self)
                    t.ai_captured_result.connect(self.digits_captured)
                    t.finished.connect(t.deleteLater)
                    self._ai_thread[cam_idx] = t
                    t.start()
            case EngineType.PYTESSERACT_OCR.value:
                    if self._ocr_thread_busy[cam_idx]:
                        prev = self._ocr_thread.get(cam_idx)
                        if prev and prev.isRunning():
                            if not prev.wait(50):
                                return

                    self._ocr_thread_busy[cam_idx] = True
                    t = RunOCRThread(widget)
                    t.setParent(self)
                    t.ocr_captured_result.connect(self.digits_captured)
                    t.finished.connect(t.deleteLater)
                    self._ocr_thread[cam_idx] = t
                    t.start()


    def digits_captured(self, rgb, cam_idx, digits):
        if not self._halt:
            getattr(self.ui, f"Cam{cam_idx}CapturedValue").setText(f"CAM{cam_idx}: {digits}")
            self._captured_digits[cam_idx] = digits
            self._captured += 1
            self._ocr_thread_busy[cam_idx] = False

        if self._captured >= 2:
            if self._captured_digits[0] != self._captured_digits[1]:
                self.onDigitsNotMatching()
            else:
                self._matchcount += 1
                self._matchcountTotal += 1
                getattr(self.ui, "Frame_Error").setStyleSheet("color: green;")
                getattr(self.ui, "Frame_Error").show()

        self.UpdateMetrics()
        
        if self._save_images:
            if self._image_thread_busy[cam_idx]:
                return

            self._image_thread_busy[cam_idx] = True
            t = RunImageThread(IMG_DIR, rgb, cam_idx, digits)
            t.setParent(self)
            t.finished.connect(self.CompletedImageThread(cam_idx))
            self._image_thread[cam_idx] = t
            t.start()


    def CompletedImageThread(self, cam_idx):
        self._image_thread_busy[cam_idx] = False


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

        self._errorcount += 1
        self._errorcountTotal += 1



    def handle_gpiotrigger(self):
        self.gpio_triggered.emit()


    def onGpioTriggered(self):
        if self._capturing and not self._halt:
            self._captured = 0
            self.calculateSpeed()

            self.CompareImages()


    def calculateSpeed(self):
        now = time.perf_counter()  # high precision time

        if self._last_time is not None:
            period = now - self._last_time  # seconds per revolution
            if period > 0:
                rps = 1 / period       # revolutions per second
                rpm = rps * 60
                self._speed = rpm

        self._last_time = now


    def StartCapturing(self):
        if self._capturing:
            self._capturing = False
            getattr(self.ui, "StartCapture").setText("Start capture")
            getattr(self.ui, "StartCapture").setIcon(QIcon(":/main/gtk-media-play-ltr.png"))
            self.ui.bStopMachine.setEnabled(True)
        else:
            self._capturing = True
            self._last_time = None
            self._matchcount = 0
            self._errorcount = 0
            getattr(self.ui, "StartCapture").setText("Stop capture")
            getattr(self.ui, "StartCapture").setIcon(QIcon(":/main/gtk-media-pause.png"))
            self.ui.bStopMachine.setEnabled(False)


    def CompareImages(self):
        for cam_idx in (0, 1):
            widget = getattr(self.ui, f"Cam{cam_idx}Source")

            match self._engine:
                case EngineType.AI_MODEL.value:
                    if self._ai_thread_busy[cam_idx]:
                        prev = self._ai_thread.get(cam_idx)
                        if prev and prev.isRunning():
                            if not prev.wait(50):
                                return

                    self._ai_thread_busy[cam_idx] = True
                    t = RunAIThread(widget)
                    t.setParent(self)
                    t.ai_captured_result.connect(self.digits_captured)
                    t.finished.connect(t.deleteLater)
                    self._ai_thread[cam_idx] = t
                    t.start()
                case EngineType.PYTESSERACT_OCR.value:
                    if self._ocr_thread_busy[cam_idx]:
                        prev = self._ocr_thread.get(cam_idx)
                        if prev and prev.isRunning():
                            if not prev.wait(50):
                                return

                    self._ocr_thread_busy[cam_idx] = True
                    t = RunOCRThread(widget)
                    t.setParent(self)
                    t.ocr_captured_result.connect(self.digits_captured)
                    t.finished.connect(t.deleteLater)
                    self._ocr_thread[cam_idx] = t
                    t.start()


    def ResetError(self):
        self.gpiooutput.on()
        self._halt = False
        getattr(self.ui, "Frame_Error").hide()
        getattr(self.ui, "ResetError").setEnabled(False)
        self.ui.bTriggerManual.setEnabled(True)
        self.ui.Cam0TestCapture.setEnabled(True)
        self.ui.Cam1TestCapture.setEnabled(True)

    
    def StartStopMachineHandler(self):
        print(f"GPIO output value: {self.gpiooutput.value}")
        if self.gpiooutput.value == 1:
            self.gpiooutput.off()
            self.ui.bStopMachine.setText("Start machine")
            self.ui.bStopMachine.setIcon(QIcon(":/main/forward.png"))
        else:
            self.gpiooutput.on()
            self.ui.bStopMachine.setText("Stop machine")
            self.ui.bStopMachine.setIcon(QIcon(":/main/dialog-cancel.png"))


    # def SaveFileDialog(self):
    #     cam_idx = int(self.sender().objectName()[3])
    #     widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

    #     self._capture_thread[cam_idx] = CaptureThread(widget)
    #     self._capture_thread[cam_idx].image_captured.connect(self.SaveFileDialogHandler)
    #     self._capture_thread[cam_idx].finished.connect(lambda: self._capture_thread[cam_idx].deleteLater())
    #     self._capture_thread[cam_idx].start()


    # def SaveFileDialogHandler(self, frame_array, cam_idx):
    #     filename, _ = QFileDialog.getSaveFileName(
    #         parent=self,
    #         caption="Save Image As...",
    #         dir="",
    #         filter="PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)",
    #         options=QFileDialog.Options()
    #     )
    #     if filename:
    #         rgb = frame_array[...,:3].copy()
    #         img = Image.fromarray(frame_array)
    #         img.save(f"{filename}.png", format="PNG")


    def UpdateMetrics(self):
        self.ui.lcdSpeed.display(self._speed)
        self.ui.lcdMatch.display(self._matchcount)
        self.ui.lcdMatchTotal.display(self._matchcountTotal)
        self.ui.lcdErrors.display(self._errorcount)
        self.ui.lcdErrorsTotal.display(self._errorcountTotal)


    def ExitApplicationHandler(self):
        self.close()


    def RebootHandler(self):
        ok = self.ask_for_password(subject="Reboot")
        if ok and self.ask_confirmation(action="reboot"):
            self.SaveSettings()
            self.gpiooutput.off()
            self.gpiotrigger.close()
            subprocess.run(["sudo", "reboot", "--reboot"])


    def ShutdownHandler(self):
        ok = self.ask_for_password(subject="Shutdown")
        if ok and self.ask_confirmation(action="shutdown"):
            self.SaveSettings()
            self.gpiooutput.off()
            self.gpiotrigger.close()
            subprocess.run(["sudo", "shutdown", "-h", "now"])


# Settings dialog, and on close
    def SettingsHandler(self):
        if not self._capturing:
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
        self._password = self._navicat_crypto.DecryptString(settings.value("password", "", type=str))
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

        settings.setValue("errorcounttotal", self._errorcountTotal)
        settings.setValue("matchcounttotal", self._matchcountTotal)


    def UnlockHandler(self):
        return self.ask_for_password(subject="Unlock Application")


    def ask_for_password(self, subject: str) -> bool:
        dlg = QInputDialog(self)  # parent = main window
        dlg.setWindowTitle(subject)
        dlg.setLabelText("Please enter the password.")
        dlg.setTextEchoMode(QLineEdit.Password)

        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setWindowFlag(Qt.Tool, True)  # stays on top of fullscreen parent

        if dlg.exec() == QInputDialog.Accepted:
            return dlg.textValue() == self._password
        return False
    

    def ask_confirmation(self, action: str) -> bool:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(f"Confirm {action}")
        msg.setText(f"Are you sure you want to {action}?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        msg.setWindowModality(Qt.ApplicationModal)
        msg.setWindowFlag(Qt.Tool, True)             # stays on top of its parent
        return msg.exec() == QMessageBox.Yes
    

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