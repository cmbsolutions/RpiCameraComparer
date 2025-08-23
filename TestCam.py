from picamera2 import Picamera2
import numpy as np
picam2 = Picamera2(1)
picam2.configure(picam2.create_preview_configuration())
picam2.start(show_preview=True)
# Check if there is AfMode available on the camera
available = picam2.camera_controls.keys()
for mode in available:
    print(mode)