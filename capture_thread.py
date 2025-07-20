from PySide6.QtCore import QObject, QThread, Signal


class CaptureThread(QThread):
    finished = Signal()
    image_captured = Signal(object, int)

    def __init__(self, picam2):
        super().__init__()
        self._picam2 = picam2

    
    def run(self):
        arr = self._picam2.capture_array()
        
        self.image_captured.emit(arr, self._picam2.camera_idx)
        self.finished.emit()