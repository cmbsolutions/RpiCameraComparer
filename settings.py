from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QDialog, QMessageBox
from PySide6.QtGui import QIcon
from settingsWindow import Ui_DialogSettings
from enumerations import EngineType

class SettingsDialog(QtWidgets.QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.ui = Ui_DialogSettings()
        self.ui.setupUi(self)

        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        
        for engine in EngineType:
            self.ui.comboBoxEngine.addItem(engine.value)

        self.ui.comboBoxEngine.setCurrentText(settings.value("engine", EngineType.PYTESSERACT_OCR.value))
        self.ui.checkBoxSaveImages.checked = settings.value("saveimages", True)
        self.ui.checkBoxClosing.checked = settings.value("is_locked", True)
        self.ui.lineEditPassword.setText(settings.value("password", "RPICameraComparer"))

        self._old_password = settings.value("password", "RPICameraComparer")

    
    def accept(self):
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        settings.value("engine", self.ui.comboBoxEngine.itemText())
        settings.value("saveimages", self.ui.checkBoxSaveImages.checked)
        settings.value("is_locked", self.ui.checkBoxClosing.checked)
        settings.value("password", self.ui.lineEditPassword.text())
        self.settings_changed.emit()
    

    def reject(self):
        return
    

    def engine_changed(self):
        return
    
    
    def closing_changed(self, CheckedState):
        return
    

    def save_changed(self, CheckedState):
        return
    
    
    def password_changed(self):
        password, ok = QInputDialog.getText(self, "Verify", "Verify the new password:", QLineEdit.Password)
        if ok and (password == self.ui.lineEditPassword.text()):
            old_password, alsook = QInputDialog.getText(self, "Old password", "Enter the old password:", QLineEdit.Password)
            if alsook and (old_password == self._old_password):
                return
            else:
                QMessageBox.critical(self, "Wrong password", "Passwords do not match.")
                self.ui.lineEditPassword.setText(self._old_password)
        else:
            QMessageBox.critical(self, "Validation error", "Passwords did not validate.")
            self.ui.lineEditPassword.setText(self._old_password)