import numpy as np
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import QRubberBand
from picamera2.previews.q_gl_picamera2 import EglState
from picamera2.previews.qt import QGlSide6Picamera2 as QGlPicamera2
from picamera2 import Preview
from libcamera import controls

_orig_create_context = EglState.create_context

def _safe_create_context(self):
    try:
        _orig_create_context(self)
    except Exception:
        pass

EglState.create_context = _safe_create_context

_orig_init_gl = QGlPicamera2.init_gl
def _safe_init_gl(self):
    try:
        _orig_init_gl(self)
    except Exception:
        pass

QGlPicamera2.init_gl = _safe_init_gl


from picamera2 import Picamera2

class QGlPicamera2(QGlPicamera2):
    def __init__(self, 
                 parent=None,
                 *,
                 camid: int = 0,
                 width: int = 640,
                 height: int = 480,
                 keep_ar: bool = True):

        self.picam2 = Picamera2(camera_num=camid)
        cfg = self.picam2.create_preview_configuration(
            main = {"size":(width, height)},
        )
        
        self.picam2.configure(cfg)

        super().__init__(self.picam2, parent=parent, width=width, height=height, keep_ar=keep_ar) 
        
        self.setMouseTracking(True)
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()

        self._frame_size = QSize(width, height)


    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._origin = ev.pos()
            self._rubber.setGeometry(QRect(self._origin, QSize()))
            self._rubber.show()

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._rubber.isVisible():
            self._rubber.setGeometry(QRect(self._origin, ev.pos()).normalized())

        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._rubber.isVisible():
            self._rubber.hide()
            rect = self._rubber.geometry()

            # map from widget coords ? frame coords
            fw, fh = self._frame_size.width(), self._frame_size.height()
            ww, wh = self.width(), self.height()
            x1 = int(rect.x() * fw / ww)
            y1 = int(rect.y() * fh / wh)
            x2 = int((rect.x()+rect.width())  * fw / ww)
            y2 = int((rect.y()+rect.height()) * fh / wh)
            
            self._roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            
            # build an RGBA overlay with a semi-transparent green box
            overlay = np.zeros((fh, fw, 4), dtype=np.uint8)
            overlay[y1:y2, x1:x2] = (0, 255, 0, 128)

            # hand it off to Picamera2
            self.set_overlay(overlay)

        super().mouseReleaseEvent(ev)

