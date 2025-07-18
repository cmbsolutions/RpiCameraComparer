import cv2
import numpy as np
from pathlib import Path

# load one example ROI (replace with your live-grabs or a saved frame)
BASE = Path(__file__).parent.resolve()
IN_DIR = BASE / "../Test"
print(f"Using output directory: {IN_DIR}")
img_color = cv2.imread(str(IN_DIR / "55572x.png"))
gray      = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

def nothing(x): pass

# create window + trackbars
cv2.namedWindow("seg")
cv2.createTrackbar("Thresh",   "seg", 0, 255, nothing)
cv2.createTrackbar("MinArea",  "seg", 50, 5000, nothing)
cv2.createTrackbar("MaxArea",  "seg", 5000, 20000, nothing)
cv2.createTrackbar("Kernel",   "seg", 1, 10, nothing)

while True:
    t = cv2.getTrackbarPos("Thresh",  "seg")
    mn= cv2.getTrackbarPos("MinArea", "seg")
    mx= cv2.getTrackbarPos("MaxArea", "seg")
    k = cv2.getTrackbarPos("Kernel",  "seg") or 1

    # simple binary invert + OTSU fallback if t==0
    if t>0:
        _, th = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY_INV)
    else:
        _, th = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)

    # morphology
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k,k))
    clean  = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

    # find contours
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        area    = w*h
        if mn < area < mx:
            cv2.rectangle(disp, (x,y), (x+w,y+h), (0,255,0), 2)

    # show side by side
    combo = np.hstack([disp, cv2.cvtColor(clean,cv2.COLOR_GRAY2BGR)])
    cv2.imshow("seg", combo)

    key = cv2.waitKey(30) & 0xFF
    if key in (27, ord('q')):
        break

cv2.destroyAllWindows()