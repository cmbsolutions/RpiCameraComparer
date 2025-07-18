import cv2

def preprocess_roi(img):
    # 1) convert to gray
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # 2) resize up so digits are bigger
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    # 3) blur out noise
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    # 4) adaptive threshold to high-contrast black/white
    th = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=11,
        C=2
    )
    # 5) optional: morphological opening to remove tiny specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    return clean


def clean_ocr(text, expected_len=5):
    # strip out anything not 0�9
    digits = ''.join(ch for ch in text if ch.isdigit())
    # if too long, take the *longest* contiguous run of length expected_len
    if len(digits) > expected_len:
        runs = [run for run in digits.split() if len(run) >= expected_len]
        if runs:
            # pick the first run of at least the right length
            digits = runs[0][:expected_len]
        else:
            digits = digits[:expected_len]
    # if too short, you could pad or mark as failed
    return digits if len(digits) == expected_len else None