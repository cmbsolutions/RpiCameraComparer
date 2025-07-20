from PySide6.QtCore import QObject, QThread, Signal
from segment_digits import ai_helper
import tensorflow as tf
from PIL import Image
import cv2

class RunAIThread(QThread):
    finished = Signal()
    ai_captured_result = Signal(object, int, str)

    def __init__(self, frame_array, cam_idx, roi, model):
        super().__init__()
        self.frame_array = frame_array
        self.idx = cam_idx
        self.roi = roi
        self.model = model

    
    def run(self):
        x1, y1, x2, y2 = self.roi
        cropped = self.frame_array[y1:y2, x1:x2]

        rois = ai_helper.segment_digits(self, cropped)
        digits = []
        for _, _, digit_img in rois:
            # resize to your CNN�s input size (64�64), normalize, etc.
            d = cv2.resize(digit_img, (64,64), interpolation=cv2.INTER_CUBIC)
            d = d.reshape(1,64,64,1)/255.0
            pred = self.model.predict(d)
            digits.append(str(pred.argmax()))
        result = "".join(digits)  

        rgb = cropped[...,:3].copy()

        self.ai_captured_result.emit(rgb, self.idx, result)
        self.finished.emit()
