from flask import Flask, Response
import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque

app = Flask(__name__)

# ROI
current_frame = None
x = 280
y = 239
w = 193
h = 98

MODEL_PATH = "models/hand_landmarker.task"

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)
]

class StableLabel:
    def __init__(self, window=10, min_count=8):
        self.window = window
        self.min_count = min_count
        self.buf = deque(maxlen=window)
        self.locked = "NONE"

    def update(self, label):
        self.buf.append(label)
        counts = {}
        for x in self.buf:
            counts[x] = counts.get(x, 0) + 1
        best = max(counts, key=counts.get)
        if counts[best] >= self.min_count and best != self.locked:
            self.locked = best
        return self.locked
    
def finger_state(hand_landmarks):
    def y(i): return hand_landmarks[i].y
    def x(i): return hand_landmarks[i].x

    index_up  = y(8)  < y(6)
    middle_up = y(12) < y(10)
    ring_up   = y(16) < y(14)
    pinky_up  = y(20) < y(18)
    thumb_up = abs(x(4) - x(2)) > 0.04  

    return {"thumb": thumb_up, "index": index_up, "middle": middle_up, "ring": ring_up, "pinky": pinky_up}

def classify_suit(hand_landmarks):
    def y(i): return hand_landmarks[i].y
    index_up  = y(8)  < y(6)
    middle_up = y(12) < y(10)
    ring_up   = y(16) < y(14)
    pinky_up  = y(20) < y(18)

    count_up = sum([index_up, middle_up, ring_up, pinky_up])

    if count_up == 4: return "HEARTS"
    if index_up and middle_up and ring_up and not pinky_up: return "SPADES"
    if index_up and not (middle_up or ring_up or pinky_up): return "CLUBS"
    if pinky_up and not (index_up or middle_up or ring_up): return "DIAMONDS"
    return "NONE"

VALUE_MAP = {1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K"}

def classify_value(hand_landmarks):
    fs = finger_state(hand_landmarks)
    code = 0
    if fs["index"]: code |= 1
    if fs["middle"]: code |= 2
    if fs["ring"]: code |= 4
    if fs["pinky"]: code |= 8
    return VALUE_MAP.get(code, "NONE")

def classify_command(hand_landmarks):
    fs = finger_state(hand_landmarks)
    
    t = fs["thumb"]
    i = fs["index"]
    m = fs["middle"]
    r = fs["ring"]
    p = fs["pinky"]

    # "Thumbs Up" gesture: ONLY the thumb is out
    if t and not (i or m or r or p):
        return "TOGGLE_ARM"
        
    return "NONE"
    
def extract_handedness(result):
    return [h[0].category_name for h in result.handedness]

def draw_hand(frame, hand_landmarks, line_color=(0, 255, 0), dot_color=(0, 0, 255)):
    h, w, _ = frame.shape
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], line_color, 2)
    for (x, y) in pts:
        cv2.circle(frame, (x, y), 3, dot_color, -1)


def generate_frames():
    global current_frame
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    timestamp_ms = 0
    value_stab = StableLabel()
    suit_stab  = StableLabel()
    cmd_stab   = StableLabel()

    armed = False
    selected = []   
    hold_counter = 0
    cooldown = 0
    
    HOLD_FRAMES = 10      
    COOLDOWN_FRAMES = 15  
    
    last_toggle_time = 0.0
    TOGGLE_COOLDOWN_SECONDS = 5.0 

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)  # selfie view
        
        # Save a clean copy of the frame BEFORE we draw anything on it for the snapshot
        current_frame = frame.copy()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        timestamp_ms += 33
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        value_raw = "NONE"
        suit_raw  = "NONE"
        cmd_raw   = "NONE"

        hands = result.hand_landmarks or []

        for hand_landmarks in hands:
            draw_hand(frame, hand_landmarks, line_color=(0,255,0), dot_color=(0,0,255))

        if hands:
            labels = extract_handedness(result)
            labels = ["Left" if hand == "Right" else "Right" for hand in labels]

            for hand_landmarks, lr in zip(hands, labels):
                if lr == "Left":
                    value_raw = classify_value(hand_landmarks)
                    cmd_raw   = classify_command(hand_landmarks) 
                elif lr == "Right":
                    suit_raw = classify_suit(hand_landmarks)

        value_stable = value_stab.update(value_raw)
        suit_stable  = suit_stab.update(suit_raw)
        cmd_stable = cmd_stab.update(cmd_raw)

        current_time = time.time()

        # clock timing i.e. not frame counting
        if cmd_stable == "TOGGLE_ARM" and (current_time - last_toggle_time) > TOGGLE_COOLDOWN_SECONDS:
            armed = not armed
            last_toggle_time = current_time
            hold_counter = 0  
        
        if cooldown > 0: 
            cooldown -= 1

        if armed and value_stable != "NONE" and suit_stable != "NONE":
            hold_counter += 1
        else:
            hold_counter = 0

        if armed and hold_counter >= HOLD_FRAMES and cooldown == 0:
            pair = (value_stable, suit_stable)
            if not selected or selected[-1] != pair:
                selected.append(pair)
            cooldown = COOLDOWN_FRAMES
            hold_counter = 0

        cv2.putText(frame, f"VALUE (Left):  {value_stable}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.putText(frame, f"SUIT  (Right): {suit_stable}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        cv2.putText(frame, f"ARMED: {armed}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0) if armed else (0,0,255), 2)
        cv2.putText(frame, f"Selected: {selected[-3:]}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        final_frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + final_frame + b'\r\n')

# --- ROUTES ---
@app.route('/')
def index():
    return '''
    <html>
      <head><title>Magic Card Robot Stream</title></head>
      <body style="background-color: #121212; color: white; text-align: center; font-family: sans-serif;">
        <h2>Live Gesture Recognition</h2>
        <img src="/video_feed" style="max-width: 80%; border: 3px solid #333; border-radius: 8px;" />
      </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snap/<card_name>')
def snap(card_name):
    global current_frame
    if current_frame is not None:
        # crop the frame
        cropped_roi = current_frame[y:y+h, x:x+w]

        # save it
        filename = f"templates/template_{card_name}.jpg"
        cv2.imwrite(filename, cropped_roi)

        return f"<h1>Success!</h1><p>Perfectly cropped and saved as <b>{filename}</b>.</p><p>You can close this tab and go back to the live stream.</p>"
    else:
        return "Camera not ready yet. Check the stream."

if __name__ == "__main__":
    print("Starting Smart Camera...")
    print("Stream: http://100.105.61.45:5000")
    print("To take a photo, open a new tab and go to: http://100.105.61.45:5000/snap/ace")
    app.run(host='0.0.0.0', port=5000, debug=False)
