from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings, Signal, Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QDialog, QMessageBox
from PySide6.QtGui import QIcon
from settingsWindow import Ui_DialogSettings
from enumerations import EngineType
from navicatEncrypt import NavicatCrypto

class SettingsDialog(QtWidgets.QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.ui = Ui_DialogSettings()
        self.ui.setupUi(self)
        self._navicat_crypto = NavicatCrypto()

        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        
        for engine in EngineType:
            self.ui.comboBoxEngine.addItem(engine.value)

        self.ui.comboBoxEngine.setCurrentText(settings.value("engine", EngineType.PYTESSERACT_OCR.value))
        self.ui.checkBoxSaveImages.setChecked(settings.value("saveimages", True, type=bool))
        self.ui.checkBoxClosing.setChecked(settings.value("is_locked", True, type=bool))
        self.ui.checkBoxPlayAudio.setChecked(settings.value("audio", True, type=bool))
        self.ui.lineEditPassword.setText(self._navicat_crypto.DecryptString(settings.value("password", "", type=str)))
        self.ui.checkBoxFullScreen.setChecked(settings.value("fullscreen", True, type=bool))

        self._old_password = self._navicat_crypto.DecryptString(settings.value("password", "", type=str))
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
    

    def accept(self):
        settings = QSettings("CMBSolutions", "RpiCameraComparer")
        settings.setValue("engine", self.ui.comboBoxEngine.currentText())
        settings.setValue("saveimages", self.ui.checkBoxSaveImages.isChecked())
        settings.setValue("is_locked", self.ui.checkBoxClosing.isChecked())
        settings.setValue("password", self._navicat_crypto.EncryptString(self.ui.lineEditPassword.text()))
        settings.setValue("audio", self.ui.checkBoxPlayAudio.isChecked())
        settings.setValue("fullscreen", self.ui.checkBoxFullScreen.isChecked())
        self.settings_changed.emit()
        super().accept()
    

    def reject(self):
        super().reject()
    

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
                self.ui.lineEditPassword.setCurrentText(self._old_password)
        else:
            QMessageBox.critical(self, "Validation error", "Passwords did not validate.")
            self.ui.lineEditPassword.setCurrentText(self._old_password)