import cv2
import numpy as np

class ai_helper:
    def __init__(self):
        super().__init__()

    def segment_digits(self, roi_img, min_area=50, max_area=5000):

        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) if roi_img.ndim == 3 else roi_img

        # 1. Gaussian blur to reduce noise
        #blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Threshold to binary image
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
 
        # 3. Morphological closing to connect broken parts (horizontal bias)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
        clean  = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

        # find contours
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

        rois = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < min_area or area > max_area:
                continue
            digit_img = gray[y:y+h, x:x+w]
            rois.append((x, w, digit_img))

        # 6. Sort left-to-right
        rois = sorted(rois, key=lambda item: item[0])
        return rois