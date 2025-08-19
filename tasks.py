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


    def run_pytesseract(self):
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


    @Slot()
    def run(self):
        try:
            frame = self._picam2.picam2.capture_array("lores")
            # if YUV420:
            H, W = self._picam2.frame  # store this at setup from your config
            gray = frame[:H, :W]
            x1, y1, x2, y2 = self._picam2.GetRoi()
            roi = gray[y1:y2, x1:x2]

            # normalize size, binarize (very fast)
            norm = cv2.resize(roi, (0,0), fx=1.5, fy=1.5, interpolation=cv2.INTER_AREA)
            _, bw = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

            api = get_api()
            # Pillow image expected by tesserocr
            pil = Image.fromarray(bw)
            api.SetImage(pil)
            text = api.GetUTF8Text().strip()
            conf = api.MeanTextConf()
            digits = ''.join(ch for ch in text if ch.isdigit())

            # If you still need RGB for painting overlays, slice from original source
            rgb = cv2.cvtColor(roi, cv2.COLOR_GRAY2RGB)  # or from color stream if you use RGB

            # quick retry if needed (bad conf or wrong length)
            if (len(digits) != 5 or conf < 70):
                # try inverted threshold (some prints are light-on-dark)
                _, bw2 = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                pil2 = Image.fromarray(bw2)
                api.SetImage(pil2)
                text2 = api.GetUTF8Text().strip()
                conf2 = api.MeanTextConf()
                digits2 = ''.join(ch for ch in text2 if ch.isdigit())
                if conf2 > conf:
                    digits, conf = digits2, conf2


            self.signals.result.emit(rgb, self._picam2.picam2.camera_idx, digits, float(conf), self._batch_id)
        except Exception as e:
            self.signals.error.emit(self._picam2.picam2.camera_idx, str(e), self._batch_id)            