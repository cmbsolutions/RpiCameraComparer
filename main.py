import sys
import re
import threading
import cv2
import numpy
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, QThread
from PySide6.QtWidgets import QFileDialog, QWidget
from PySide6.QtGui import QIcon
from qglpicamera2_wrapper import QGlPicamera2
from mainWindow import Ui_MainWindow
from functools import partial
from libcamera import controls
from capture_thread import CaptureThread
from run_ocr_thread import RunOCRThread
from run_ai_thread import RunAIThread
from PIL import Image
from segment_digits import ai_helper
import tensorflow as tf
import pytesseract
from enumerations import EngineType
from pathlib import Path
from gpiozero import Button, OutputDevice

# ───── Configuration ─────
TRIGGER_PIN = 4
OUTPUT_PIN = 27
PULSE_TIME = 0.5  # seconds

BASE = Path(__file__).parent.resolve()
IMG_DIR = BASE / "Captures"
IMG_DIR.mkdir(parents=True, exist_ok=True)


# ----- Main class -----
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.Frame_Error.hide()
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        self._lens_pos = [float(settings.value(f"lensposition/{i}", 0.0)) for i in (0, 1)]
        self._focus_supported = {}
        self._frame_array = {}
        self.collecting = False
        self.ocr_lock = threading.Lock()
        self.predict_lock = threading.Lock()
        self._capture_thread = {}
        self._ocr_thread = {}
        self._ai_thread = {}
        self._capturing = False
        self._captured_digits = {}
        self._captured = 0
        self._halt = False
        self._engine = EngineType.PYTESSERACT_OCR
        self._save_images = True

        for engine in EngineType:
            getattr(self.ui, "cbRecogniser").addItem(engine.value)

        # This is the AI model
        self._model = tf.keras.models.load_model("ai_model/digit_cnn_model5.keras")
        
        # Setup GPIO
        self.gpiotrigger = Button(TRIGGER_PIN, pull_up=True)
        self.gpiooutput = OutputDevice(OUTPUT_PIN)
        self.gpiotrigger.when_pressed = self.handle_gpiotrigger

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


    def ResetCamRoi(self, checked: bool):
        cam_index = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_index}Source")
        widget.set_overlay(None)

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

        widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

        # thread = QThread()
        # worker = CaptureThread(widget)
        # worker.moveToThread(thread)
        # thread.started.connect(worker.run)
        # worker.image_captured.connect(self.handleCaptured)
        # worker.finished.connect(thread.quit)
        # worker.finished.connect(worker.deleteLater)
        # thread.finished.connect(thread.deleteLater)
        # thread.start()

        self._capture_thread[cam_idx] = CaptureThread(widget)
        self._capture_thread[cam_idx].image_captured.connect(self.handleCaptured)
        self._capture_thread[cam_idx].finished.connect(lambda: lambda: self._capture_thread[cam_idx].deleteLater())
        self._capture_thread[cam_idx].start()

# Callback from capture_array from camera
    def handleCaptured(self, frame_array, cam_idx):
        self._cam_idx = cam_idx
        self._frame_array[cam_idx] = frame_array
        roi = getattr(self.ui, f"Cam{cam_idx}Source")._roi

        match self._engine:
            case EngineType.AI_MODEL:
                # thread = QThread()
                # worker = RunAIThread(frame_array, cam_idx, roi, self._model)
                # worker.moveToThread(thread)
                # thread.started.connect(worker.run)
                # worker.ai_captured_result.connect(self.digits_captured)
                # worker.finished.connect(thread.quit)
                # worker.finished.connect(worker.deleteLater)
                # thread.finished.connect(thread.deleteLater)
                # thread.start()

                self._ai_thread[cam_idx] = RunAIThread(frame_array, cam_idx, roi, self._model)
                self._ai_thread[cam_idx].ai_captured_result.connect(self.digits_captured)
                self._ai_thread[cam_idx].finished.connect(lambda: self._ai_thread[cam_idx].deleteLater())
                self._ai_thread[cam_idx].start()
            case EngineType.PYTESSERACT_OCR:
                # thread = QThread()
                # worker = RunOCRThread(frame_array, cam_idx, roi)
                # worker.moveToThread(thread)
                # thread.started.connect(worker.run)
                # worker.ocr_captured_result.connect(self.digits_captured)
                # worker.finished.connect(thread.quit)
                # worker.finished.connect(worker.deleteLater)
                # thread.finished.connect(thread.deleteLater)
                # thread.start()
                
                self._ocr_thread[cam_idx] = RunOCRThread(frame_array, cam_idx, roi)
                self._ocr_thread[cam_idx].ocr_captured_result.connect(self.digits_captured)
                self._ocr_thread[cam_idx].finished.connect(lambda: self._ocr_thread[cam_idx].deleteLater())
                self._ocr_thread[cam_idx].start()


    def digits_captured(self, rgb, cam_idx, digits):
        if not self._halt:
            getattr(self.ui, f"Cam{cam_idx}CapturedValue").setText(f"CAM{cam_idx}: {digits}")
            self._captured_digits[cam_idx] = digits
            self._captured += 1

        if self._save_images:
            img = Image.fromarray(rgb)
            img.save(IMG_DIR / f"{digits}.png", format="PNG")

        if self._captured >= 2:
            if self._captured_digits[0] != self._captured_digits[1]:
                self._halt = True
                getattr(self.ui, "Frame_Error").setStyleSheet("color: red;")
                getattr(self.ui, "Frame_Error").show()
                getattr(self.ui, "ResetError").setEnabled(True)
            else:
                getattr(self.ui, "Frame_Error").setStyleSheet("color: green;")
                getattr(self.ui, "Frame_Error").show()


    def handle_gpiotrigger(self):
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

            #QtCore.QTimer.singleShot(500, self.CompareImages)


    def CompareImages(self):
        for idx in (0, 1):
            widget = getattr(self.ui, f"Cam{idx}Source").picam2

            # thread = QThread()
            # worker = CaptureThread(widget)
            # worker.moveToThread(thread)
            # thread.started.connect(worker.run)
            # worker.image_captured.connect(self.handleCaptured)
            # worker.finished.connect(thread.quit)
            # worker.finished.connect(worker.deleteLater)
            # thread.finished.connect(thread.deleteLater)
            # thread.start()

            self._capture_thread[idx] = CaptureThread(widget)
            self._capture_thread[idx].image_captured.connect(self.handleCaptured)
            self._capture_thread[idx].finished.connect(lambda: self._capture_thread[idx].quit())
            self._capture_thread[idx].start()

        #if self._capturing and not self._halt:
            #QtCore.QTimer.singleShot(500, self.CompareImages)


    def ResetError(self):
        getattr(self.ui, f"Frame_Error").hide()
        getattr(self.ui, f"ResetError").setEnabled(False)
        self._halt = False
        #if self._capturing:
            #QtCore.QTimer.singleShot(1000, self.CompareImages)

    
    def SaveFileDialog(self):
        cam_idx = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

        # thread = QThread()
        # worker = CaptureThread(widget)
        # worker.moveToThread(thread)
        # thread.started.connect(worker.run)
        # worker.image_captured.connect(self.SaveFileDialogHandler)
        # worker.finished.connect(thread.quit)
        # worker.finished.connect(worker.deleteLater)
        # thread.finished.connect(thread.deleteLater)
        # thread.start()

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
            options=QFileDialog.Options()  # you can OR in flags like DontUseNativeDialog
        )
        if filename:
            rgb = frame_array[...,:3].copy()
            img = Image.fromarray(frame_array)
            img.save(f"{filename}.png", format="PNG")


    def ChangeEngine(self):
        selected_text = getattr(self.ui, self.sender().objectName()).currentText()
        for engine in EngineType:
            if engine.value == selected_text:
                self._engine = engine
                break


    def ChangeSaveImg(self, idx):
        self._save_images = getattr(self.ui, self.sender().objectName()).checked()


    def closeEvent(self, event):
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        for idx in (0, 1):
            settings.setValue(f"lensposition/{idx}", self._lens_pos[idx])
        super().closeEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())