import pytesseract
import cv2
import os
import time
from pathlib import Path

def preprocess_image(img):
# Ensure grayscale
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Normalize brightness (convert to float, then rescale)
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

    # Apply simple global threshold (Otsu)
    _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return img


# Path to the folder with images
BASE = Path(__file__).parent.resolve()
IMG_DIR = BASE / "img2"
print(f"Using input directory: {IMG_DIR}")

# Tesseract config
tess_config = "--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789"

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
    raw = cv2.imread(str(img_path))
    img = preprocess_image(raw)

    # OCR
    ocr_result = pytesseract.image_to_string(img, config=tess_config)
    ocr_digits = ''.join(filter(str.isdigit, ocr_result)).strip()

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


