#!/usr/bin/bash

pyside6-uic ./mainWindow.ui -o mainWindow.py
pyside6-uic ./settingsWindow.ui -o settingsWindow.py
pyside6-rcc ./Resources/icons.qrc -o ./icons_rc.py