import cv2
import os
import glob
import numpy as np
import time

# --- ROI SETTINGS (Must match your snap script!) ---
# x = 260
# y = 248
# w = 232
# h = 89
x = 280
y = 239
w = 193
h = 98

FINAL_SIZE = 160
PAD = 8

# --- 1. LOAD THE DICTIONARY ---
templates = {}
print("Loading dictionary...")
files = glob.glob("processed/*.jpg") + glob.glob("processed/*.png")

for path in files:
    # Clean up the name for printing (e.g., "template_ace_spades.jpg" -> "ace_spades")
    clean_name = os.path.basename(path).replace("template_", "").replace(".jpg", "").replace(".png", "")
    # Load as grayscale
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is not None:
        templates[clean_name] = img
        print(f"Loaded: {clean_name}")

if not templates:
    print("ERROR: No templates found in the 'processed' folder!")
    exit()

# --- 2. PREPROCESSING FUNCTION (Adapted for Live Video) ---
def preprocess_live_roi(cropped_bgr):
    gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    ys, xs = np.where(thresh > 0)
    if len(xs) == 0 or len(ys) == 0:
        return None

    x1, x2 = xs.min(), xs.max()
    y1, y2 = ys.min(), ys.max()

    x1 = max(0, x1 - PAD)
    y1 = max(0, y1 - PAD)
    x2 = min(thresh.shape[1] - 1, x2 + PAD)
    y2 = min(thresh.shape[0] - 1, y2 + PAD)

    cropped = thresh[y1:y2+1, x1:x2+1]
    
    h_crop, w_crop = cropped.shape
    scale = min((FINAL_SIZE - 2*PAD) / w_crop, (FINAL_SIZE - 2*PAD) / h_crop)
    
    new_w = max(1, int(round(w_crop * scale)))
    new_h = max(1, int(round(h_crop * scale)))
    
    resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    
    canvas = np.zeros((FINAL_SIZE, FINAL_SIZE), dtype=np.uint8)
    x_off = (FINAL_SIZE - new_w) // 2
    y_off = (FINAL_SIZE - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    
    return canvas

# --- 3. THE MAIN CAMERA LOOP ---
print("Warming up camera...")
cap = cv2.VideoCapture(0)
time.sleep(2)
print("Camera active! Drop a card into the chute. Press Ctrl+C to quit.")

try:
    while True:
        success, frame = cap.read()
        if not success:
            continue

        # Grab just the green box area
        roi = frame[y:y+h, x:x+w]
        
        # Turn the live feed into a 160x160 black/white canvas
        live_canvas = preprocess_live_roi(roi)

        if live_canvas is not None:
            best_score = -1.0
            best_match = "Unknown"

            # Compare it against every template in the dictionary
            for name, template_img in templates.items():
                # TM_CCOEFF_NORMED returns a score between -1.0 and 1.0 (1.0 is perfect)
                res = cv2.matchTemplate(live_canvas, template_img, cv2.TM_CCOEFF_NORMED)
                score = res[0][0]
                
                if score > best_score:
                    best_score = score
                    best_match = name

            # Only print if we are somewhat confident (cuts down on blank-space noise)
            if best_score > 0.50:
                print(f"Detected: {best_match.upper()} (Confidence: {best_score:.2f})")
            
        # Sleep for a fraction of a second so we don't flood your terminal screen
        time.sleep(0.25)

except KeyboardInterrupt:
    print("\nShutting down matcher...")
finally:
    cap.release()
