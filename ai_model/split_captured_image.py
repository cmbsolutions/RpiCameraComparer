import cv2
import numpy as np
from pathlib import Path


def extract_and_normalize_digits(img, output_size=(32, 32), digit_count=5):
    # Convert to grayscale if needed
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # Apply binary thresholding (tweak threshold if needed)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    digit_images = []
    bounding_boxes = []

    # Filter and collect bounding boxes
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > 10 and w > 5:  # Filter out noise (tweak as needed)
            bounding_boxes.append((x, y, w, h))

    # Sort left to right
    bounding_boxes = sorted(bounding_boxes, key=lambda b: b[0])

    # Check if we got expected number of digits
    if len(bounding_boxes) != digit_count:
        print(f"[Warning] Expected {digit_count} digits but found {len(bounding_boxes)}.")
        # Optionally: return or pad/truncate

    for x, y, w, h in bounding_boxes[:digit_count]:
        digit = thresh[y:y+h, x:x+w]

        # Make square
        size = max(w, h)
        square = np.full((size, size), 0, dtype=np.uint8)  # black background
        x_offset = (size - w) // 2
        y_offset = (size - h) // 2
        square[y_offset:y_offset+h, x_offset:x_offset+w] = digit

        # Resize to 32x32
        resized = cv2.resize(square, output_size, interpolation=cv2.INTER_AREA)
        digit_images.append(resized)

    return digit_images


# load one example ROI (replace with your live-grabs or a saved frame)
BASE = Path(__file__).parent.resolve()
IN_DIR = BASE / "../Captures"
print(f"Using output directory: {IN_DIR}")
img_color = cv2.imread(str(IN_DIR / "0_33610_0000.png"))
gray      = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
digits = extract_and_normalize_digits(gray)

for i, digit in enumerate(digits):
    cv2.imwrite(str(IN_DIR / f"digit_{i}.png"), digit)