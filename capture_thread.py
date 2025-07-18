from PySide6.QtCore import QThread, Signal


class CaptureThread(QThread):
    imgage_captured = Signal(object, int)

    def __init__(self, picam2):
        super().__init__()
        self._picam2 = picam2

    
    def run(self):
        arr = self._picam2.capture_array()
        
        self.imgage_captured.emit(arr, self._picam2.camera_idx)