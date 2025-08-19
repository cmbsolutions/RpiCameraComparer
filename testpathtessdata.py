from pathlib import Path
import os

# Path to the folder with images
BASE = Path("/usr/share/tesseract-ocr/5/tessdata").resolve()
print(f"Using input directory: {BASE}")

# Process images
for img_path in BASE.glob("*"):
    print(f"Found file: {img_path.name}")