from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import numpy as np
import random
from pathlib import Path
import os

FONT_PATH = "/usr/share/fonts/truetype/msttcorefonts/"  # adjust as needed
# 1) Figure out where *this* script lives, and make TrainingSet there
BASE = Path(__file__).parent.resolve()
OUT_DIR = BASE / "TrainingSet6"
print(f"Using output directory: {OUT_DIR}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

fontsize=32

#for fnt in ("cour", "arial", "times", "verdana"):
fnt = "arial"
font = ImageFont.truetype(f"{FONT_PATH}{fnt}.ttf", size=fontsize)  # pick a size similar to your ROIs

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

        # save
        img.save(class_dir / f"{digit}_{fnt}_{i:04d}.png")