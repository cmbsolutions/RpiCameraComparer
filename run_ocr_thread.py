from PySide6.QtCore import QObject, QThread, Signal
import pytesseract
from PIL import Image
import cv2
from qglpicamera2_wrapper import QGlPicamera2

class RunOCRThread(QThread):
    finished = Signal()
    ocr_captured_result = Signal(object, int, str)


    def __init__(self, picam2):
        super().__init__()
        self._picam2 = picam2

    
    def run(self):
        frame_array = self._picam2.picam2.capture_array()

        x1, y1, x2, y2 = self._picam2.GetRoi()
        cropped = frame_array[y1:y2, x1:x2]
        gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
        digits = ''.join(filter(str.isdigit, text))

        rgb = cropped[...,:3].copy()
        
        print(f"OCR Cam{self._picam2.picam2.camera_idx}")
        self.ocr_captured_result.emit(rgb, self._picam2.picam2.camera_idx, digits)
        print(f"OCR Cam{self._picam2.picam2.camera_idx} finished")
        self.finished.emit()
