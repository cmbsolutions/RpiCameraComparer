# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settingsWindow.ui'
##
## Created by: Qt User Interface Compiler version 6.8.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLayout, QLineEdit, QSizePolicy, QWidget)

class Ui_DialogSettings(object):
    def setupUi(self, DialogSettings):
        if not DialogSettings.objectName():
            DialogSettings.setObjectName(u"DialogSettings")
        DialogSettings.setWindowModality(Qt.WindowModality.ApplicationModal)
        DialogSettings.resize(401, 269)
        DialogSettings.setModal(True)
        self.buttonBox = QDialogButtonBox(DialogSettings)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setGeometry(QRect(0, 230, 391, 32))
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.formLayoutWidget = QWidget(DialogSettings)
        self.formLayoutWidget.setObjectName(u"formLayoutWidget")
        self.formLayoutWidget.setGeometry(QRect(10, 10, 381, 211))
        self.formLayout = QFormLayout(self.formLayoutWidget)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.formLayoutWidget)
        self.label.setObjectName(u"label")
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label)

        self.comboBoxEngine = QComboBox(self.formLayoutWidget)
        self.comboBoxEngine.setObjectName(u"comboBoxEngine")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.comboBoxEngine)

        self.label_2 = QLabel(self.formLayoutWidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_2)

        self.checkBoxClosing = QCheckBox(self.formLayoutWidget)
        self.checkBoxClosing.setObjectName(u"checkBoxClosing")
        self.checkBoxClosing.setChecked(False)

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.checkBoxClosing)

        self.label_3 = QLabel(self.formLayoutWidget)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.label_3)

        self.checkBoxSaveImages = QCheckBox(self.formLayoutWidget)
        self.checkBoxSaveImages.setObjectName(u"checkBoxSaveImages")

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.checkBoxSaveImages)

        self.checkBoxPlayAudio = QCheckBox(self.formLayoutWidget)
        self.checkBoxPlayAudio.setObjectName(u"checkBoxPlayAudio")

        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.checkBoxPlayAudio)

        self.label_5 = QLabel(self.formLayoutWidget)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.label_5)

        self.label_4 = QLabel(self.formLayoutWidget)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.label_4)

        self.lineEditPassword = QLineEdit(self.formLayoutWidget)
        self.lineEditPassword.setObjectName(u"lineEditPassword")
        self.lineEditPassword.setMaxLength(25)
        self.lineEditPassword.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.lineEditPassword.setCursorMoveStyle(Qt.CursorMoveStyle.LogicalMoveStyle)
        self.lineEditPassword.setClearButtonEnabled(False)

        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.lineEditPassword)


        self.retranslateUi(DialogSettings)
        self.comboBoxEngine.currentIndexChanged.connect(DialogSettings.engine_changed)
        self.checkBoxClosing.checkStateChanged.connect(DialogSettings.closing_changed)
        self.checkBoxSaveImages.checkStateChanged.connect(DialogSettings.save_changed)
        self.lineEditPassword.editingFinished.connect(DialogSettings.password_changed)

        QMetaObject.connectSlotsByName(DialogSettings)
    # setupUi

    def retranslateUi(self, DialogSettings):
        DialogSettings.setWindowTitle(QCoreApplication.translate("DialogSettings", u"RPICameraComparer Settings", None))
        self.label.setText(QCoreApplication.translate("DialogSettings", u"Engine :", None))
        self.comboBoxEngine.setCurrentText("")
        self.label_2.setText(QCoreApplication.translate("DialogSettings", u"No closing :", None))
        self.checkBoxClosing.setText("")
        self.label_3.setText(QCoreApplication.translate("DialogSettings", u"Save images", None))
        self.checkBoxSaveImages.setText("")
        self.checkBoxPlayAudio.setText("")
        self.label_5.setText(QCoreApplication.translate("DialogSettings", u"Play audio", None))
        self.label_4.setText(QCoreApplication.translate("DialogSettings", u"Unlock password :", None))
        self.lineEditPassword.setText(QCoreApplication.translate("DialogSettings", u"password", None))
    # retranslateUi

