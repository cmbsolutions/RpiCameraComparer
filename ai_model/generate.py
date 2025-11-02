from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import random
from pathlib import Path
import os
import cv2

FONT_PATH = "/usr/share/fonts/truetype/msttcorefonts/"  # adjust as needed
# 1) Figure out where *this* script lives, and make TrainingSet there
BASE = Path(__file__).parent.resolve()
OUT_DIR = BASE / "TrainingSet8"
print(f"Using output directory: {OUT_DIR}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

fontsize=24

#for fnt in ("cour", "arial", "times", "verdana"):
fnt = "arial"
font = ImageFont.truetype(f"{FONT_PATH}{fnt}.ttf", size=fontsize)  # pick a size similar to your ROIs

def motion_blur_cv(img_pil, length=15, angle=0.0, linewidth=1):
    """
    Apply Photoshop-like motion blur using OpenCV's filter2D.
    - length: streak length in pixels (>=1)
    - angle: degrees CCW (0 = horizontal blur to the right)
    - linewidth: line thickness of the PSF
    """
    # Ensure valid sizes
    length = max(1, int(length))
    linewidth = max(1, int(linewidth))
    size = length * 2 + 1  # make the kernel square & odd

    # 1) Build a horizontal line PSF (Point Spread Function)
    psf = np.zeros((size, size), dtype=np.float32)
    c = size // 2
    cv2.line(psf, (c - length//2, c), (c + length//2, c), 1.0, thickness=linewidth)

    # 2) Rotate PSF to requested angle
    M = cv2.getRotationMatrix2D((c, c), angle, 1.0)  # CCW degrees
    psf = cv2.warpAffine(psf, M, (size, size), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # 3) Normalize so sum == 1 (preserve brightness)
    s = psf.sum()
    if s > 0:
        psf /= s
    else:
        psf[c, c] = 1.0  # fallback

    # 4) Run the convolution on the image with filter2D
    img = np.array(img_pil.convert("RGB"))  # H�W�3 uint8
    blurred = cv2.filter2D(img, ddepth=-1, kernel=psf)  # -1 keeps uint8

    return Image.fromarray(blurred, mode="RGB")

for digit in range(10):
    class_dir = OUT_DIR / str(digit)
    class_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1000):  # 1000 samples per digit
        # create blank white image
        img = Image.new("L", (64,64), color=255)
        draw = ImageDraw.Draw(img)

        # random horizontal/vertical jitter up to �5 px
        cx, cy = 32, 32
        dx = np.random.randint(-5, 5)
        dy = np.random.randint(-5, 5)

        draw.text(
            (cx+dx,cy+dy),
            str(digit),
            font=font,
            fill=0,
            anchor="mm",
        )
        
        # optional: rotate a bit
        angle = np.random.uniform(-10, 10)
        img = img.rotate(
            angle,
            resample=Image.BICUBIC,
            fillcolor=255
        )

        # Generate a random brightness factor (e.g., between 0.5 and 1.5)
        brightness_factor = random.uniform(0.5, 1.5)

        # Enhance the brightness
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness_factor)

        img = motion_blur_cv(img, length=random.randint(2,7), angle=0.0, linewidth=random.randint(1,3))

        # save
        img.save(class_dir / f"{digit}_{i:04d}.png")