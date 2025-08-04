import sys
import cv2
import numpy as np
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt, QUrl
from PySide6.QtWidgets import QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QWidget
from PySide6.QtGui import QPixmap, QImage
from ai_prediction_viewer import Ui_MainWindowAI
import tensorflow as tf
from PIL import Image
from pathlib import Path
from segment_digits import ai_helper


BASE = Path(__file__).parent.resolve()
IMG_DIR = BASE / "../Tests"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# ----- Main class -----
class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindowAI()
        self.ui.setupUi(self)

        self._model = tf.keras.models.load_model("./digit_cnn_model7.keras")
        self._sourcefile = ""


    def LoadSourceHandler(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select an image file",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            self._sourcefile = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scene = QGraphicsScene()
                item = QGraphicsPixmapItem(pixmap)
                scene.addItem(item)
                self.ui.img1_2.setScene(scene)
                self.ui.img1_2.fitInView(item)  # Optional: scale to fit


    def PredictHandler(self):
        img = cv2.imread(self._sourcefile)

        segments = ai_helper.segment_digits(self, img)

        digits = []
        idx = 0
        for _, _, digit_img in segments:
            pixmap = self.numpy_to_pixmap(digit_img)
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(pixmap)
            scene.addItem(item)
            getattr(self.ui, f"img{idx+1}").setScene(scene)
            getattr(self.ui, f"img{idx+1}").fitInView(item)

            # resize to your CNN�s input size (64�64), normalize, etc.
            d = cv2.resize(digit_img, (64,64), interpolation=cv2.INTER_CUBIC)
            d = d.reshape(1,64,64,1)/255.0
            pred = self._model.predict(d)
            print(f"Prediction for digit {idx+1}: {pred.argmax()}")
            digits.append(str(pred.argmax()))
            getattr(self.ui, f"lbl{idx+1}").setText(digits[idx])
            idx += 1
        ocr_digits = "".join(digits)  


    def numpy_to_pixmap(self, img):
        img = np.ascontiguousarray(img)
        height, width = img.shape
        bytes_per_line = width
        qimage = QImage(img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        return QPixmap.fromImage(qimage)
    

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())