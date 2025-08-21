import sys
import os
import re
import subprocess
import time
import itertools
import tensorflow as tf
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt, QUrl, QThreadPool
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QSoundEffect
from qglpicamera2_wrapper import QGlPicamera2
from mainWindow import Ui_MainWindow
from libcamera import controls
from run_ocr_thread import RunOCRThread
from run_ai_thread import RunAIThread
from run_image_thread import RunImageThread
from enumerations import EngineType
from pathlib import Path
from gpiozero import Button, OutputDevice
from settings import SettingsDialog
from navicatEncrypt import NavicatCrypto
from tasks import OCRTask
from dialogs import Dialogs

#os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/5"
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
os.environ.setdefault("OMP_NUM_THREADS",  "1")


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
        self._speed_perminute = 0.0
        self._matched = 0
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
        if self._engine == EngineType.AI_MODEL.value:
            self._model = tf.keras.models.load_model("ai_model/digit_cnn_model7.keras")
        else:
            self._model = None

        self.gpio_triggered.connect(self.onGpioTriggered)

        # Setup GPIO
        self.gpiotrigger = Button(TRIGGER_PIN, pull_up=True, bounce_time=0.05)
        self.gpiooutput = OutputDevice(OUTPUT_PIN)
        self.gpiooutput.on()
        self.gpiotrigger.when_pressed = self.handle_gpiotrigger

        if self._fullscreen:
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.showFullScreen()

        QtCore.QTimer.singleShot(20, self._insert_cameras)
    

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
        self.setup_ocr_parallel()


# Setup OCR parallel processing
    # This is used to run OCR tasks in parallel using QRunnable and QThreadPool
    # It allows us to capture images from both cameras and process them without blocking the UI
    def setup_ocr_parallel(self):
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(2)
        self.cam_widgets = {0: self.ui.Cam0Source, 1: self.ui.Cam1Source}
        self._ocr_busy = {0: False, 1: False}
        self._pending = {}
        self._batch_counter = itertools.count(1)


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
            self._matched += 1

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


# halt the machine
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


# GPIO trigger handler
    def handle_gpiotrigger(self):
        self.gpio_triggered.emit()


# This is called when the GPIO trigger is pressed
    def onGpioTriggered(self):
        if self._halt or not self._capturing:
            return
        
        if any(self._ocr_busy.values()):
            return
        
        self._captured = 0
        self.calculateSpeed()

        batch_id = next(self._batch_counter)
        self._pending[batch_id] = {}

        for cam_idx, w in self.cam_widgets.items():
            self._ocr_busy[cam_idx] = True
            task = OCRTask(w, batch_id)
            task.signals.result.connect(self._on_ocr_result, Qt.QueuedConnection)
            task.signals.error.connect(self._on_ocr_error, Qt.QueuedConnection)
            self.pool.start(task)


    def _on_ocr_result(self, rgb, cam_idx, digits, conf, batch_id):
        self._ocr_busy[cam_idx] = False
        bucket = self._pending.get(batch_id)
        if bucket is None:
            return
        bucket[cam_idx] = (rgb, digits, conf)
        if len(bucket) == 2:
                (rgb0, d0, c0) = bucket[0]
                (rgb1, d1, c1) = bucket[1]
                ok = (len(d0)==5 and len(d1)==5 and d0 == d1 and c0 >= 70 and c1 >= 70)
                self._finalize_pair(batch_id, ok, (d0,c0), (d1,c1), (rgb0,rgb1))
                self._pending.pop(batch_id, None)
            

    def _on_ocr_error(self, cam_idx, msg, batch_id):
        self._ocr_busy[cam_idx] = False
        print(f"OCR error cam{cam_idx}: {msg}")
        # finalize with whatever we got (optional)
        self._finalize_pair(batch_id, False, ("",0.0), ("",0.0), (None,None))
        self._pending.pop(batch_id, None)


    def _finalize_pair(self, batch_id, ok, left, right, rgbs):
        (d0,c0), (d1,c1) = left, right

        if ok:
            if not self._halt:
                self.ui.Cam0CapturedValue.setText(f"CAM0: {d0}")
                self.ui.Cam1CapturedValue.setText(f"CAM1: {d1}")
                self._captured_digits[0] = d0
                self._captured_digits[1] = d1

                if d0 != d1:
                    self.onDigitsNotMatching()
                else:
                    self._matched += 1
                    self._matchcount += 1
                    self._matchcountTotal += 1
                    getattr(self.ui, "Frame_Error").setStyleSheet("color: green;")
                    getattr(self.ui, "Frame_Error").show()
            else:
                return
        else:
            self.onDigitsNotMatching()

        self.UpdateMetrics()


    def calculateSpeed(self):
        now = time.perf_counter()  # high precision time

        if self._last_time is not None:
            period = now - self._last_time  # seconds per revolution
            if period > 0:
                rps = 1 / period       # revolutions per second
                rpm = rps * 60
                self._speed = rpm
                if self._matched > 0:
                    mps = self._matched
                    self._speed_perminute = mps * period
                    self._mached = 0

        self._last_time = now


    def StartCapturing(self):
        if self._capturing:
            self._capturing = False
            getattr(self.ui, "StartCapture").setText("Start capture")
            getattr(self.ui, "StartCapture").setIcon(QIcon(":/main/gtk-media-play-ltr.png"))
            self.ui.bStopMachine.setEnabled(True)
            self._timer.stop()
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
        self._last_time = None

    
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


    def UpdateMetrics(self):
        self.ui.lcdSpeed.display(self._speed)
        self.ui.lcdMatch.display(self._matchcount)
        self.ui.lcdMatchTotal.display(self._matchcountTotal)
        self.ui.lcdErrors.display(self._errorcount)
        self.ui.lcdErrorsTotal.display(self._errorcountTotal)
        self.ui.lcdSpeed_perminute.display(self._speed_perminute)    


    def ExitApplicationHandler(self):
        self.close()


    def RebootHandler(self):
        pwentry = Dialogs.ask_for_password(self, subject="Reboot")
        ok = pwentry == self._password
        if ok and Dialogs.ask_confirmation(self, "reboot"):
            self.SaveSettings()
            self.gpiooutput.off()
            self.gpiotrigger.close()
            subprocess.run(["sudo", "reboot", "--reboot"])


    def ShutdownHandler(self):
        pwentry = Dialogs.ask_for_password(self, subject="Shutdown")
        ok = pwentry == self._password
        if ok and Dialogs.ask_confirmation(self, "Shutdown"):
            self.SaveSettings()
            self.gpiooutput.off()
            self.gpiotrigger.close()
            subprocess.run(["sudo", "shutdown", "-h", "now"])


# Settings dialog, and on close
    def SettingsHandler(self):
        if not self._capturing:
            if self._is_locked:
                pwentry = Dialogs.ask_for_password(self, subject="Modify settings")
                ok = pwentry == self._password
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

        if self._engine == EngineType.AI_MODEL.value and self._model is None:
            self._model = tf.keras.models.load_model("ai_model/digit_cnn_model7.keras")


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
        pwentry = Dialogs.ask_for_password(self, subject="Unlock Application")
        return pwentry == self._password
    

    def closeEvent(self, event):
        if self._is_locked:
            pwentry = Dialogs.ask_for_password(self, subject="Exit Application")
            if pwentry != self._password:
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


    def TimerHandler(self):
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.handle_gpiotrigger)
        self._timer.start(500)


    def TimerDialHandler(self, time_ms):
        if self._timer.isActive():
            self._timer.stop()
        self._timer.setInterval(time_ms * 10)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())