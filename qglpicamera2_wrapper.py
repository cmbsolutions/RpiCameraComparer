import numpy as np
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import QRubberBand
from picamera2.previews.qt import QGlSide6Picamera2 as QGlPicamera2
from picamera2 import Preview
from libcamera import controls
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
            self.set_roi(rect)

        super().mouseReleaseEvent(ev)


    def GetRoi(self):
        return self._roi


    def set_roi(self, roi_rect=None):
        fw, fh = self._frame_size.width(), self._frame_size.height()
        ww, wh = self.width(), self.height()
        x_offset = (ww - fw) // 2
        y_offset = (wh - fh) // 2

        if roi_rect is not None and isinstance(roi_rect, QRect):
            # Coming from mouse event
            x1 = int((roi_rect.x() - x_offset))
            y1 = int((roi_rect.y() - y_offset))
            x2 = int((roi_rect.x() + roi_rect.width() - x_offset))
            y2 = int((roi_rect.y() + roi_rect.height() - y_offset))

            # Clamp to frame
            x1 = max(0, min(x1, fw - 1))
            y1 = max(0, min(y1, fh - 1))
            x2 = max(0, min(x2, fw - 1))
            y2 = max(0, min(y2, fh - 1))

            self._roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        elif roi_rect is not None:
            # Coming from settings (tuple)
            self._roi = roi_rect
        # else leave as is
        self.update_overlay()


    def update_overlay(self):
        if self._roi is None:
            self.set_overlay(None)
            return
        fw, fh = self._frame_size.width(), self._frame_size.height()
        x1, y1, x2, y2 = self._roi
        overlay = np.zeros((fh, fw, 4), dtype=np.uint8)
        overlay[y1:y2, x1:x2] = (0, 255, 0, 128)
        self.set_overlay(overlay)

