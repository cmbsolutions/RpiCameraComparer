from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox


class Dialogs:
    def __init__(self):
        super().__init__()


    def ask_for_password(self, subject: str) -> str:
        dlg = QInputDialog(self)  # parent = main window
        dlg.setWindowTitle(subject)
        dlg.setLabelText("Please enter the password.")
        dlg.setTextEchoMode(QLineEdit.Password)

        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setWindowFlag(Qt.Tool, True)  # stays on top of fullscreen parent

        if dlg.exec() == QInputDialog.Accepted:
            return dlg.textValue()
        return ""
    

    def ask_confirmation(self, action: str) -> bool:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(f"Confirm {action}")
        msg.setText(f"Are you sure you want to {action}?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        msg.setWindowModality(Qt.ApplicationModal)
        msg.setWindowFlag(Qt.Tool, True)             # stays on top of its parent
        return msg.exec() == QMessageBox.Yes


    def display_error_message(self, message: str) -> bool:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(f"Critial Error")
        msg.setText(f"{message}")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)

        msg.setWindowModality(Qt.ApplicationModal)
        msg.setWindowFlag(Qt.Tool, True)             # stays on top of its parent
        return msg.exec() == QMessageBox.Ok
