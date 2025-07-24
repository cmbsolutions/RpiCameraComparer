#!/usr/bin/bash

pyinstaller --noconfirm --onefile --windowed --exclude-module PyQt5 --exclude-module PyQt5.QtCore --exclude-module PyQt5.QtGui --exclude-module PyQt5.QtWidgets --add-data "ai_model/digit_cnn_model6.keras:ai_model/digit_cnn_model6.keras" main.py