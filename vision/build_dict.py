import cv2
import os
import glob
import numpy as np

RAW_DIR = "templates"
OUT_DIR = "processed"
FINAL_SIZE = 160
PAD = 8

os.makedirs(OUT_DIR, exist_ok=True)

def preprocess_template(path):
    img = cv2.imread(path)
    if img is None:
        print(f"Could not read {path}")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Mild blur
    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    # Otsu threshold
    _, thresh = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # Mild cleanup only
    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # Find all white pixels
    ys, xs = np.where(thresh > 0)
    if len(xs) == 0 or len(ys) == 0:
        print(f"No ink found in {path}")
        return None

    x1, x2 = xs.min(), xs.max()
    y1, y2 = ys.min(), ys.max()

    # Crop with small padding
    x1 = max(0, x1 - PAD)
    y1 = max(0, y1 - PAD)
    x2 = min(thresh.shape[1] - 1, x2 + PAD)
    y2 = min(thresh.shape[0] - 1, y2 + PAD)

    cropped = thresh[y1:y2+1, x1:x2+1]

    # Preserve aspect ratio on fixed canvas
    h, w = cropped.shape
    scale = min((FINAL_SIZE - 2*PAD) / w, (FINAL_SIZE - 2*PAD) / h)

    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

    canvas = np.zeros((FINAL_SIZE, FINAL_SIZE), dtype=np.uint8)
    x_off = (FINAL_SIZE - new_w) // 2
    y_off = (FINAL_SIZE - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized

    return canvas


files = glob.glob(os.path.join(RAW_DIR, "*.jpg")) + glob.glob(os.path.join(RAW_DIR, "*.png"))

if not files:
    print("No template images found in templates/")
else:
    print(f"Found {len(files)} template image(s).")

for path in files:
    processed = preprocess_template(path)
    name = os.path.basename(path)

    if processed is None:
        print(f"Skipped {name}")
        continue

    out_path = os.path.join(OUT_DIR, name)
    cv2.imwrite(out_path, processed)
    print(f"Saved processed template: {out_path}")

print("Done.")
