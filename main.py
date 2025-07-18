import sys
import re
import threading
import cv2
import numpy
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QFileDialog, QWidget
from qglpicamera2_wrapper import QGlPicamera2
from mainWindow import Ui_MainWindow
from functools import partial
from libcamera import controls
from capture_thread import CaptureThread
from PIL import Image
from segment_digits import ai_helper
import tensorflow as tf
import pytesseract
from enumerations import EngineType

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.Frame_Error.hide()
        self._lens_pos = {}
        self._focus_supported = {}
        self.collecting = False
        self.ocr_lock = threading.Lock()
        self.predict_lock = threading.Lock()
        self._capture_thread = None
        self._capturing = False
        self._halt = False
        self._engine = EngineType.AI_MODEL

        for engine in EngineType:
            getattr(self.ui, "cbRecogniser").addItem(engine.value)

        # This is the AI model
        self._model = tf.keras.models.load_model("ai_model/digit_cnn_model5.keras")
        
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

    
    def TestCam(self, checked: bool):
        cam_idx = int(self.sender().objectName()[3])

        getattr(self.ui, f"Cam{cam_idx}TestCapture").setEnabled(False)

        widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

        self._capture_thread = CaptureThread(widget)
        self._capture_thread.imgage_captured.connect(self.handleCaptured)
        self._capture_thread.finished.connect(lambda: getattr(self.ui, f"Cam{cam_idx}TestCapture").setEnabled(True))
        self._capture_thread.start()


    def handleCaptured(self, frame_array, cam_idx):
        self._cam_idx = cam_idx
        self._frame_array = frame_array

        match self._engine:
            case EngineType.AI_MODEL:
                threading.Thread(target=self.predict_roi_digits).start()
            case EngineType.PYTESSERACT_OCR:
                threading.Thread(target=self.run_dual_ocr).start() 

    
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

        print(f"Camera {cam_idx} focus set to {pos:.2f}")


    def CamOnFocusSlider(self):
        cam_idx = int(self.sender().objectName()[3])
        widget = getattr(self.ui, f"Cam{cam_idx}Slider")

        pos = self._lens_pos[cam_idx] = widget.value()/10
        self._lens_pos[cam_idx] = pos
        getattr(self.ui, f"Cam{cam_idx}Source").picam2.set_controls({"LensPosition": pos})

        print(f"Camera {cam_idx} focus set to {pos:.2f}")


    def StartCapturing(self):
        if self._capturing:
            self._capturing = False
        else:
            self._capturing = True
            QtCore.QTimer.singleShot(500, self.CompareImages)


    def CompareImages(self):
        for idx in (0, 1):
            widget = getattr(self.ui, f"Cam{idx}Source").picam2

            self._capture_thread = CaptureThread(widget)
            self._capture_thread.imgage_captured.connect(self.handleCaptured)
            self._capture_thread.finished.connect(lambda: getattr(self.ui, f"Cam{idx}TestCapture").setEnabled(True))
            self._capture_thread.start()
            break

        if self._capturing and not self._halt:
            QtCore.QTimer.singleShot(500, self.CompareImages)


    def ResetError(self):
        getattr(self.ui, f"Frame_Error").hide()
        getattr(self.ui, f"ResetError").setEnabled(False)
        self._halt = False
        if self._capturing:
            QtCore.QTimer.singleShot(1000, self.CompareImages)

    
    def SaveFileDialog(self):
        cam_idx = int(self.sender().objectName()[3])
        getattr(self.ui, f"Cam{cam_idx}TestCapture").setEnabled(False)
        widget = getattr(self.ui, f"Cam{cam_idx}Source").picam2

        self._capture_thread = CaptureThread(widget)
        self._capture_thread.imgage_captured.connect(self.SaveFileDialogHandler)
        self._capture_thread.finished.connect(lambda: getattr(self.ui, f"Cam{cam_idx}TestCapture").setEnabled(True))
        self._capture_thread.start()


    def SaveFileDialogHandler(self, frame_array, cam_idx):
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image As...",
            dir="",
            filter="PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)",
            options=QFileDialog.Options()  # you can OR in flags like DontUseNativeDialog
        )
        if filename:
            img = Image.fromarray(frame_array, mode="RGBA")
            img.save(f"{filename}.png", format="PNG")


    def ChangeEngine(self):
        selected_text = getattr(self.ui, self.sender().objectName()).currentText()
        for engine in EngineType:
            if engine.value == selected_text:
                self._engine = engine
                break


    def run_dual_ocr(self):
        with self.ocr_lock:
            roi = getattr(self.ui, f"Cam{self._cam_idx}Source")._roi
            #roi2 = getattr(self.ui, f"Cam{self._cam_idx+1}Source")._roi

            
            x1, y1, x2, y2 = roi
            cropped = self._frame_array[y1:y2, x1:x2]
            gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
            text = pytesseract.image_to_string(gray, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
            digits1 = ''.join(filter(str.isdigit, text))

            #digits2 = extract_digits(self._frame_array, roi2)

            #digits1 = ocr_preprocess.clean_ocr(digits1)
            #digits2 = ocr_preprocess.clean_ocr(digits2)
            
            if not self._halt:
                getattr(self.ui, f"Cam{self._cam_idx}CapturedValue").setText(f"CAM{self._cam_idx}: {digits1}")
                #getattr(self.ui, f"Cam{self._cam_idx+1}CapturedValue").setText(f"CAM{self._cam_idx+1}: {digits2}")
            
            img = Image.fromarray(cropped, mode="RGBA")
            img.save(f"Test/{digits1}.png", format="PNG")
            #if digits1 != digits2:
            #    getattr(self.ui, f"Frame_Error").show()
            #    getattr(self.ui, f"ResetError").setEnabled(True)
            #    self._halt = True


    def predict_roi_digits(self):
        with self.predict_lock:
            roi = getattr(self.ui, f"Cam{self._cam_idx}Source")._roi

            x1, y1, x2, y2 = roi
            cropped = self._frame_array[y1:y2, x1:x2]

            rois = ai_helper.segment_digits(self, cropped)
            digits = []
            for _, _, digit_img in rois:
                # resize to your CNN�s input size (64�64), normalize, etc.
                d = cv2.resize(digit_img, (32,32), interpolation=cv2.INTER_CUBIC)
                d = d.reshape(1,32,32,1)/255.0
                pred = self._model.predict(d)
                digits.append(str(pred.argmax()))
            result = "".join(digits)  

            img = Image.fromarray(cropped, mode="RGBA")
            img.save(f"Test/{result}.png", format="PNG")

            if not self._halt:
                getattr(self.ui, f"Cam{self._cam_idx}CapturedValue").setText(f"CAM{self._cam_idx}: {result}")     


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())