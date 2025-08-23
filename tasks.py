import threading
from tesserocr import PyTessBaseAPI, PSM, OEM
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
import pytesseract
from PIL import Image
import cv2
from qglpicamera2_wrapper import QGlPicamera2

_tls = threading.local()

def get_api():
    api = getattr(_tls, "api", None)
    if api is None:
        api = PyTessBaseAPI(lang='eng', oem=OEM.LSTM_ONLY)  # fast; try LSTM_ONLY to compare
        api.SetPageSegMode(PSM.SINGLE_LINE)  # PSM 7
        api.SetVariable("tessedit_char_whitelist", "0123456789")
        api.SetVariable("load_system_dawg", "F")
        api.SetVariable("load_freq_dawg", "F")
        api.SetVariable("classify_bln_numeric_mode", "T")
        _tls.api = api
    return api  
      

class OCRSignals(QObject):
    result = Signal(object, int, str, float, int)
    error = Signal(int, str, int)


class OCRTask(QRunnable):
    def __init__(self, picam2, batch_id):
        super().__init__()
        self._picam2 = picam2
        self._batch_id = batch_id
        self.signals = OCRSignals()


    def runx(self):
        try:
            frame_array = self._picam2.picam2.capture_array()
            x1, y1, x2, y2 = self._picam2.GetRoi()
            cropped = frame_array[y1:y2, x1:x2]
            gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
            text = pytesseract.image_to_string(gray, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
            digits = ''.join(filter(str.isdigit, text))

            rgb = cropped[...,:3].copy()

            self.signals.result.emit(rgb, self._picam2.picam2.camera_idx, digits, 100.0, self._batch_id)            
        except Exception as e:
            self.signals.error.emit(self._picam2.picam2.camera_idx, str(e), 0.0, self._batch_id)


    def run(self):
        try:
            frame_array = self._picam2.picam2.capture_array()
            x1, y1, x2, y2 = self._picam2.GetRoi()
            cropped = frame_array[y1:y2, x1:x2]
            gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)

            api = get_api()
            # Pillow image expected by tesserocr
            pil = Image.fromarray(gray)
            api.SetImage(pil)
            text = api.GetUTF8Text().strip()
            conf = api.MeanTextConf()
            digits = ''.join(ch for ch in text if ch.isdigit())


            # quick retry if needed (bad conf or wrong length)
            if (len(digits) != 5 or conf < 70):
                print(f"Retrying OCR for camera {self._picam2.picam2.camera_idx} with conf {conf} and digits '{digits}'")
                pil2 = Image.fromarray(gray)
                api.SetImage(pil2)
                text2 = api.GetUTF8Text().strip()
                conf2 = api.MeanTextConf()
                digits2 = ''.join(ch for ch in text2 if ch.isdigit())
                if conf2 > conf:
                    digits, conf = digits2, conf2

            # If you still need RGB for painting overlays, slice from original source
            rgb = cropped[...,:3].copy()

            self.signals.result.emit(rgb, self._picam2.picam2.camera_idx, digits, float(conf), self._batch_id)
        except Exception as e:
            self.signals.error.emit(self._picam2.picam2.camera_idx, str(e), self._batch_id)            