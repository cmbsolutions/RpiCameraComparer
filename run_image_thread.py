from PySide6.QtCore import QThread, Signal
from PIL import Image
from pathlib import Path

class RunImageThread(QThread):
    finished = Signal()


    def __init__(self, imgdir, rgb, cam_idx, digits):
        super().__init__()
        self._rgb= rgb
        self._cam_idx = cam_idx
        self._digits = digits
        self._imgdir = imgdir

    
    def run(self):
        fileindex = 0

        while True:
            filename = f"{self._cam_idx}_{self._digits}_{fileindex:04d}.png"
            file_path = Path(self._imgdir) / filename
            if not file_path.exists():
                img = Image.fromarray(self._rgb)
                img.save(file_path, format="PNG")
                break
            fileindex += 1
        
        print(f"Saving image finished")
        self.finished.emit()
