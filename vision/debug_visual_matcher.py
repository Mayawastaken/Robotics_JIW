from flask import Flask, Response
import cv2
import time
import os
import glob
import numpy as np

app = Flask(__name__)

# --- ROI SETTINGS ---
x = 260
y = 248
w = 232
h = 89

FINAL_SIZE = 160
PAD = 8

# --- 1. LOAD THE DICTIONARY ---
templates = {}
print("Loading dictionary...")
files = glob.glob("processed/*.jpg") + glob.glob("processed/*.png")

for path in files:
    clean_name = os.path.basename(path).replace("template_", "").replace(".jpg", "").replace(".png", "")
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is not None:
        templates[clean_name] = img
        print(f"Loaded: {clean_name}")

if not templates:
    print("ERROR: No templates found! Run your preprocess script first.")
    exit()

# --- 2. PREPROCESSING FUNCTION ---
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

# --- 3. THE FLASK CAMERA LOOP ---
print("Warming up camera...")
cap = cv2.VideoCapture(0)
time.sleep(2)

def generate_frames():
    # Timer for the terminal diagnostic feed
    last_log_time = time.time() 
    
    while True:
        success, frame = cap.read()
        if not success:
            break

        roi = frame[y:y+h, x:x+w]
        live_canvas = preprocess_live_roi(roi)

        best_score = -1.0
        best_match = "Scanning..."

        # Calculate all scores and sort them
        if live_canvas is not None:
            scores = []
            for name, template_img in templates.items():
                res = cv2.matchTemplate(live_canvas, template_img, cv2.TM_CCOEFF_NORMED)
                scores.append((name, float(res[0][0])))
            
            # Sort the list from highest score to lowest score
            scores.sort(key=lambda x: x[1], reverse=True)
            best_match, best_score = scores[0]

            # --- TERMINAL DIAGNOSTIC LOGIC (Always prints Top 3 every 1s) ---
            current_time = time.time()
            if current_time - last_log_time > 1.0:
                print("\n--- SENSOR READOUT ---")
                for name, score in scores[:3]:
                    print(f"  {name}: {score:.3f}")
                last_log_time = current_time

        # --- BROWSER VIDEO LOGIC (Only shows > 75%) ---
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        if best_score > 0.75:
            display_text = f"{best_match.upper()} ({int(best_score*100)}%)"
            cv2.rectangle(frame, (x, y-30), (x+w, y), (0, 0, 0), -1)
            cv2.putText(frame, display_text, (x+5, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        final_frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + final_frame + b'\r\n')

@app.route('/')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print("Starting Advanced Visual Matcher...")
    print("Video Stream: http://100.105.61.45:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
