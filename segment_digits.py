import cv2
import numpy as np

class ai_helper:
    def __init__(self):
        super().__init__()

    def segment_digits(self, roi_img, min_area=100, max_area=5000):
        """
        Given a color or gray ROI containing 1�5 digits in roughly a row,
        return a list of (x, w, digit_img) tuples, sorted by x.
        """
        # 1) Preprocess
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) \
            if roi_img.ndim == 3 else roi_img
        # increase contrast & binarize
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        _, th = cv2.threshold(blur, 0, 255,
                            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

        # 2) Morphological closing to join broken strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        closed = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 3) Find contours
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)

        rois = []
        for cnt in contours:
            x,y,w,h = cv2.boundingRect(cnt)
            area = w*h
            # filter out noise or huge background blobs
            if area < min_area or area > max_area:
                continue
            # Extract the digit sub-image, pad it a little
            pad = 2
            x0, y0 = max(0, x-pad), max(0, y-pad)
            x1, y1 = min(gray.shape[1], x+w+pad), min(gray.shape[0], y+h+pad)
            digit_img = gray[y0:y1, x0:x1]
            rois.append((x0, w, digit_img))

        # 4) Sort left-to-right by the x coordinate
        rois = sorted(rois, key=lambda item: item[0])
        return rois