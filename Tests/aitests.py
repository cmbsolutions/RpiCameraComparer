import tensorflow as tf
import cv2
import numpy as np
from pathlib import Path
import os
import time


def segment_digits(roi_img, min_area=50, max_area=5000):
    gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) if roi_img.ndim == 3 else roi_img

    # 1. Gaussian blur to reduce noise
    # blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # 2. Threshold to binary image
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # 3. Morphological closing to connect broken parts (horizontal bias)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    clean = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

    # find contours
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    rois = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        if area < min_area or area > max_area:
            continue
        digit_img = gray[y:y + h, x:x + w]
        rois.append((x, w, digit_img))

    # 6. Sort left-to-right
    rois = sorted(rois, key=lambda item: item[0])
    return rois


def center_and_pad(img, size=64):
    h, w = img.shape
    canvas = np.full((size, size), 255, dtype=np.uint8)  # white background
    y_offset = (size - h) // 2
    x_offset = (size - w) // 2
    canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img
    return canvas


# Path to the folder with images
BASE = Path(__file__).parent.resolve()
IMG_DIR = BASE / "img3"
print(f"Using input directory: {IMG_DIR}")

#AI Model
model = tf.keras.models.load_model(BASE / "../ai_model/digit_cnn_model7.keras")

# Stats
correct = 0
errors = 0
total = 0

start_time = time.time()

# Process images
for img_path in IMG_DIR.glob("*.png"):
    total += 1
    # Get expected value from filename (first 5 digits)
    expected = img_path.name[:5]

    # Read and preprocess image
    img = cv2.imread(str(img_path))
    #img = preprocess_image(raw)

    segments = segment_digits(img)
    digits = []
    for _, _, digit_img in segments:
        digit_img = center_and_pad(digit_img)
        # resize to your CNN�s input size (64�64), normalize, etc.
        d = cv2.resize(digit_img, (64,64), interpolation=cv2.INTER_CUBIC)
        d = d.reshape(1,64,64,1)/255.0
        pred = model.predict(d)
        digits.append(str(pred.argmax()))
    ocr_digits = "".join(digits)  

    # Compare
    if ocr_digits == expected:
        correct += 1
    else:
        errors += 1
        print(f"[ERROR] {img_path.name} ? expected: {expected}, got: {ocr_digits}")

# End timing
end_time = time.time()
duration = end_time - start_time
fps = total / duration if duration > 0 else 0

# Final report
print(f"\n? Correct: {correct}")
print(f"? Errors:  {errors}")
print(f"?? Total images: {total}")
print(f"?? Time taken: {duration:.2f} seconds")
print(f"? Performance: {fps:.2f} images/second")