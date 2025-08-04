# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ai_prediction_viewer.ui'
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
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGridLayout, QLabel,
    QLayout, QMainWindow, QMenuBar, QPushButton,
    QSizePolicy, QStatusBar, QWidget)

class Ui_MainWindowAI(object):
    def setupUi(self, MainWindowAI):
        if not MainWindowAI.objectName():
            MainWindowAI.setObjectName(u"MainWindowAI")
        MainWindowAI.resize(800, 600)
        icon = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.ViewFullscreen))
        MainWindowAI.setWindowIcon(icon)
        self.centralwidget = QWidget(MainWindowAI)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayoutWidget = QWidget(self.centralwidget)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(9, 9, 781, 191))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.img3 = QGraphicsView(self.gridLayoutWidget)
        self.img3.setObjectName(u"img3")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.img3.sizePolicy().hasHeightForWidth())
        self.img3.setSizePolicy(sizePolicy)
        self.img3.setMinimumSize(QSize(128, 128))
        self.img3.setMaximumSize(QSize(128, 128))

        self.gridLayout.addWidget(self.img3, 0, 4, 1, 1)

        self.img4 = QGraphicsView(self.gridLayoutWidget)
        self.img4.setObjectName(u"img4")
        sizePolicy.setHeightForWidth(self.img4.sizePolicy().hasHeightForWidth())
        self.img4.setSizePolicy(sizePolicy)
        self.img4.setMinimumSize(QSize(128, 128))
        self.img4.setMaximumSize(QSize(128, 128))

        self.gridLayout.addWidget(self.img4, 0, 5, 1, 1)

        self.img1 = QGraphicsView(self.gridLayoutWidget)
        self.img1.setObjectName(u"img1")
        sizePolicy.setHeightForWidth(self.img1.sizePolicy().hasHeightForWidth())
        self.img1.setSizePolicy(sizePolicy)
        self.img1.setMinimumSize(QSize(128, 128))
        self.img1.setMaximumSize(QSize(128, 128))

        self.gridLayout.addWidget(self.img1, 0, 2, 1, 1)

        self.img2 = QGraphicsView(self.gridLayoutWidget)
        self.img2.setObjectName(u"img2")
        sizePolicy.setHeightForWidth(self.img2.sizePolicy().hasHeightForWidth())
        self.img2.setSizePolicy(sizePolicy)
        self.img2.setMinimumSize(QSize(128, 128))
        self.img2.setMaximumSize(QSize(128, 128))

        self.gridLayout.addWidget(self.img2, 0, 3, 1, 1)

        self.img5 = QGraphicsView(self.gridLayoutWidget)
        self.img5.setObjectName(u"img5")
        sizePolicy.setHeightForWidth(self.img5.sizePolicy().hasHeightForWidth())
        self.img5.setSizePolicy(sizePolicy)
        self.img5.setMinimumSize(QSize(128, 128))
        self.img5.setMaximumSize(QSize(128, 128))

        self.gridLayout.addWidget(self.img5, 0, 6, 1, 1)

        self.lbl1 = QLabel(self.gridLayoutWidget)
        self.lbl1.setObjectName(u"lbl1")
        self.lbl1.setMaximumSize(QSize(128, 128))
        font = QFont()
        font.setFamilies([u"Liberation Mono"])
        font.setPointSize(40)
        font.setBold(True)
        self.lbl1.setFont(font)
        self.lbl1.setScaledContents(False)
        self.lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.lbl1, 1, 2, 1, 1)

        self.lbl2 = QLabel(self.gridLayoutWidget)
        self.lbl2.setObjectName(u"lbl2")
        self.lbl2.setMaximumSize(QSize(128, 128))
        self.lbl2.setFont(font)
        self.lbl2.setScaledContents(False)
        self.lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.lbl2, 1, 3, 1, 1)

        self.lbl3 = QLabel(self.gridLayoutWidget)
        self.lbl3.setObjectName(u"lbl3")
        self.lbl3.setMaximumSize(QSize(128, 128))
        self.lbl3.setFont(font)
        self.lbl3.setScaledContents(False)
        self.lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.lbl3, 1, 4, 1, 1)

        self.lbl4 = QLabel(self.gridLayoutWidget)
        self.lbl4.setObjectName(u"lbl4")
        self.lbl4.setMaximumSize(QSize(128, 128))
        self.lbl4.setFont(font)
        self.lbl4.setScaledContents(False)
        self.lbl4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.lbl4, 1, 5, 1, 1)

        self.lbl5 = QLabel(self.gridLayoutWidget)
        self.lbl5.setObjectName(u"lbl5")
        self.lbl5.setMaximumSize(QSize(128, 128))
        self.lbl5.setFont(font)
        self.lbl5.setScaledContents(False)
        self.lbl5.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.lbl5, 1, 6, 1, 1)

        self.gridLayout.setRowStretch(1, 1)
        self.gridLayoutWidget_2 = QWidget(self.centralwidget)
        self.gridLayoutWidget_2.setObjectName(u"gridLayoutWidget_2")
        self.gridLayoutWidget_2.setGeometry(QRect(10, 210, 781, 191))
        self.gridLayout_2 = QGridLayout(self.gridLayoutWidget_2)
        self.gridLayout_2.setSpacing(6)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.img1_2 = QGraphicsView(self.gridLayoutWidget_2)
        self.img1_2.setObjectName(u"img1_2")
        sizePolicy.setHeightForWidth(self.img1_2.sizePolicy().hasHeightForWidth())
        self.img1_2.setSizePolicy(sizePolicy)
        self.img1_2.setMinimumSize(QSize(256, 128))
        self.img1_2.setMaximumSize(QSize(128, 128))

        self.gridLayout_2.addWidget(self.img1_2, 0, 0, 1, 1)

        self.bPredict = QPushButton(self.gridLayoutWidget_2)
        self.bPredict.setObjectName(u"bPredict")

        self.gridLayout_2.addWidget(self.bPredict, 1, 1, 1, 1)

        self.bLoad = QPushButton(self.gridLayoutWidget_2)
        self.bLoad.setObjectName(u"bLoad")

        self.gridLayout_2.addWidget(self.bLoad, 1, 0, 1, 1)

        MainWindowAI.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindowAI)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 19))
        MainWindowAI.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindowAI)
        self.statusbar.setObjectName(u"statusbar")
        MainWindowAI.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindowAI)
        self.bLoad.clicked.connect(MainWindowAI.LoadSourceHandler)
        self.bPredict.clicked.connect(MainWindowAI.PredictHandler)

        QMetaObject.connectSlotsByName(MainWindowAI)
    # setupUi

    def retranslateUi(self, MainWindowAI):
        MainWindowAI.setWindowTitle(QCoreApplication.translate("MainWindowAI", u"AI Prediction viewer", None))
        self.lbl1.setText(QCoreApplication.translate("MainWindowAI", u"1", None))
        self.lbl2.setText(QCoreApplication.translate("MainWindowAI", u"1", None))
        self.lbl3.setText(QCoreApplication.translate("MainWindowAI", u"1", None))
        self.lbl4.setText(QCoreApplication.translate("MainWindowAI", u"1", None))
        self.lbl5.setText(QCoreApplication.translate("MainWindowAI", u"1", None))
        self.bPredict.setText(QCoreApplication.translate("MainWindowAI", u"Predict", None))
        self.bLoad.setText(QCoreApplication.translate("MainWindowAI", u"Load source", None))
    # retranslateUi

