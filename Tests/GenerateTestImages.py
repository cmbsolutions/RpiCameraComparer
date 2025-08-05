from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import numpy as np
import random
from pathlib import Path
import os

FONT_PATH = "c:/windows/fonts/"  # adjust as needed
# 1) Figure out where *this* script lives, and make TrainingSet there
BASE = Path(__file__).parent.resolve()
OUT_DIR = BASE / "img3"
print(f"Using output directory: {OUT_DIR}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

fontsize=24

#for fnt in ("cour", "arial", "times", "verdana"):
fnt = "Arial"
font = ImageFont.truetype(f"{FONT_PATH}{fnt}.TTF", size=fontsize)  # pick a size similar to your ROIs

for i in range(1000):
    digits = ""
    for y in range(5):
        digits += str(np.random.randint(0, 9))

    # create blank white image
    img = Image.new("L", (128,64), color=255)
    draw = ImageDraw.Draw(img)

    # random horizontal/vertical jitter up to �5 px
    cx, cy = 64, 32
    dx = np.random.randint(-10, 10)
    dy = np.random.randint(-10, 10)

    draw.text(
        (cx+dx,cy+dy),
        digits,
        font=font,
        fill=0,
        anchor="mm",
    )
    
    # optional: rotate a bit
    angle = np.random.uniform(-1, 1)
    img = img.rotate(
        angle,
        resample=Image.BICUBIC,
        fillcolor=255
    )

    # Generate a random brightness factor (e.g., between 0.5 and 1.5)
    brightness_factor = random.uniform(0.1, 2.0)

    # Enhance the brightness
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness_factor)

    # save
    img.save(OUT_DIR / f"{digits}_{i:04d}.png")