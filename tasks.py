from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
import pytesseract
from PIL import Image
import cv2
from qglpicamera2_wrapper import QGlPicamera2


class OCRSignals(QObject):
    result = Signal(object, int, str, int)
    error = Signal(int, str, int)


class OCRTask(QRunnable):
    def __init__(self, picam2, batch_id):
        super().__init__()
        self._picam2 = picam2
        self._batch_id = batch_id
        self.signals = OCRSignals()


    def run(self):
        try:
            frame_array = self._picam2.picam2.capture_array()
            x1, y1, x2, y2 = self._picam2.GetRoi()
            cropped = frame_array[y1:y2, x1:x2]
            gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
            text = pytesseract.image_to_string(gray, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
            digits = ''.join(filter(str.isdigit, text))

            rgb = cropped[...,:3].copy()

            self.signals.result.emit(rgb, self._picam2.picam2.camera_idx, digits, self._batch_id)            
        except Exception as e:
            self.signals.error.emit(self._picam2.picam2.camera_idx, str(e), self._batch_id)