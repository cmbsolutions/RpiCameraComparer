from PySide6.QtCore import QObject, QThread, Signal
from segment_digits import ai_helper
import tensorflow as tf
from PIL import Image
import cv2
from qglpicamera2_wrapper import QGlPicamera2

class RunAIThread(QThread):
    finished = Signal()
    ai_captured_result = Signal(object, int, str)

    def __init__(self, picam2, model):
        super().__init__()
        self._picam2 = picam2
        self._model = model

    
    def run(self):
        frame_array = self._picam2.picam2.capture_array()

        x1, y1, x2, y2 = self._picam2.GetRoi()
        cropped = frame_array[y1:y2, x1:x2]

        segments = ai_helper.segment_digits(self, cropped)
        digits = []
        for _, _, digit_img in segments:
            # resize to your CNN�s input size (64�64), normalize, etc.
            d = cv2.resize(digit_img, (64,64), interpolation=cv2.INTER_CUBIC)
            d = d.reshape(1,64,64,1)/255.0
            pred = self._model.predict(d)
            digits.append(str(pred.argmax()))
        result = "".join(digits)  

        rgb = cropped[...,:3].copy()

        print(f"AI Cam{self._picam2.picam2.camera_idx}")
        self.ai_captured_result.emit(rgb, self._picam2.picam2.camera_idx, result)
        print(f"AI Cam{self._picam2.picam2.camera_idx} finished")
        self.finished.emit()
