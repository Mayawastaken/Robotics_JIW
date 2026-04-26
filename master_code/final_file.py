from flask import Flask, Response
import cv2
import time
import os
import glob
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque
import board
import busio
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685

app = Flask(__name__)

# ==========================================
# 0. ROBUST PATH HANDLING
# ==========================================
# Dynamically anchors paths to the project root so the script can be 
# reliably executed from any working directory or systemd service.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "hand_landmarker.task")
VISION_DIR = os.path.join(PROJECT_ROOT, "vision", "processed")

# ==========================================
# 1. HARDWARE SETTINGS & INITIALIZATION
# ==========================================
SERVO_MIN = 150
SERVO_MAX = 600
SERVO_FREQ = 50

# DC Gear Motor (Friction rollers)
MOTOR_IN1 = 5
MOTOR_IN2 = 6
MOTOR_SPEED = 70 

# I2C PCA9685 Servo Assignments
servo_1_port = 0  # THE SORTER FLAP: Gates cards to Accept/Reject bins
servo_2_port = 1  # THE DISPENSER KICKER: Maintains dispensing rhythm

# Absolute angles mapped to physical chassis calibration
SERVO_1_CENTER = 99
SERVO_1_STATE_A = 70   # ACCEPT (-29 deg from center)
SERVO_1_STATE_B = 126  # REJECT (+27 deg from center)

SERVO_2_CENTER = 90
SERVO_2_RIGHT = 5      # PUSH STROKE

# Init GPIO for DC Motor
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_IN1, GPIO.OUT)
GPIO.setup(MOTOR_IN2, GPIO.OUT)
GPIO.output(MOTOR_IN1, GPIO.LOW)
motor_pwm = GPIO.PWM(MOTOR_IN2, 1000)
motor_pwm.start(0) # Start in OFF state

# Init I2C for Servos
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = SERVO_FREQ

def move_servo_to(port, degrees):
    """Converts a standard 0-180 degree angle to a PCA9685 PWM pulse length."""
    pulse_length = SERVO_MIN + (degrees / 180.0) * (SERVO_MAX - SERVO_MIN)
    duty_cycle = int((pulse_length / 4096.0) * 65535)
    pca.channels[port].duty_cycle = duty_cycle

# Safety: Center servos on boot
move_servo_to(servo_1_port, SERVO_1_CENTER)
move_servo_to(servo_2_port, SERVO_2_CENTER)

# ==========================================
# 2. VISION SETTINGS & GLOBALS
# ==========================================
system_state = "GESTURE" # FSM State Tracking
selected_cards = []      # Target Queue, e.g., [('A', 'HEARTS')]

# Camera 0 Data (Gesture Model & Hand Connections)
HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16), (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)]
VALUE_MAP = {1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K"}

# Camera 1 Data (Template Matching ROI)
cam1_x, cam1_y, cam1_w, cam1_h = 274, 248, 218, 89
FINAL_SIZE = 160
PAD = 8

# Load Card Templates into memory (Pre-processed Binary Images)
templates = {}
print(f"Loading dictionary from {VISION_DIR}...")
files = glob.glob(os.path.join(VISION_DIR, "*.jpg")) + glob.glob(os.path.join(VISION_DIR, "*.png"))
for path in files:
    clean_name = os.path.basename(path).replace("template_", "").replace(".jpg", "").replace(".png", "")
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is not None:
        templates[clean_name] = img
        print(f"Loaded: {clean_name}")

if not templates:
    print("WARNING: No card templates found!")

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
class StableLabel:
    """A deque-based buffer to debounce computer vision classifications."""
    def __init__(self, window=10, min_count=8):
        self.window, self.min_count, self.buf, self.locked = window, min_count, deque(maxlen=window), "NONE"
    def update(self, label):
        self.buf.append(label)
        counts = {x: self.buf.count(x) for x in self.buf}
        best = max(counts, key=counts.get)
        if counts[best] >= self.min_count and best != self.locked: self.locked = best
        return self.locked

def finger_state(hand_landmarks):
    y, x = lambda i: hand_landmarks[i].y, lambda i: hand_landmarks[i].x
    return {"thumb": abs(x(4) - x(2)) > 0.04, "index": y(8) < y(6), "middle": y(12) < y(10), "ring": y(16) < y(14), "pinky": y(20) < y(18)}

def classify_value(hand_landmarks):
    """4-bit binary encoding using Left Hand fingers."""
    fs, code = finger_state(hand_landmarks), 0
    if fs["index"]: code |= 1
    if fs["middle"]: code |= 2
    if fs["ring"]: code |= 4
    if fs["pinky"]: code |= 8
    return VALUE_MAP.get(code, "NONE")

def classify_suit(hand_landmarks):
    fs = finger_state(hand_landmarks)
    count_up = sum([fs["index"], fs["middle"], fs["ring"], fs["pinky"]])
    if count_up == 4: return "HEARTS"
    if fs["index"] and fs["middle"] and fs["ring"] and not fs["pinky"]: return "SPADES"
    if fs["index"] and not (fs["middle"] or fs["ring"] or fs["pinky"]): return "CLUBS"
    if fs["pinky"] and not (fs["index"] or fs["middle"] or fs["ring"]): return "DIAMONDS"
    return "NONE"

def classify_command(hand_landmarks):
    fs = finger_state(hand_landmarks)
    if fs["thumb"] and not (fs["index"] or fs["middle"] or fs["ring"] or fs["pinky"]): return "TOGGLE_ARM"
    return "NONE"

def draw_hand(frame, hand_landmarks):
    h, w, _ = frame.shape
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]
    for a, b in HAND_CONNECTIONS: cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
    for (x, y) in pts: cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

def preprocess_live_roi(cropped_bgr):
    """Isolates the card shape, normalizes size, and applies Otsu's thresholding."""
    gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.where(thresh > 0)
    if len(xs) == 0 or len(ys) == 0: return None
    x1, y1 = max(0, xs.min() - PAD), max(0, ys.min() - PAD)
    x2, y2 = min(thresh.shape[1] - 1, xs.max() + PAD), min(thresh.shape[0] - 1, ys.max() + PAD)
    cropped = thresh[y1:y2+1, x1:x2+1]
    scale = min((FINAL_SIZE - 2*PAD) / cropped.shape[1], (FINAL_SIZE - 2*PAD) / cropped.shape[0])
    new_w, new_h = max(1, int(round(cropped.shape[1] * scale))), max(1, int(round(cropped.shape[0] * scale)))
    resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((FINAL_SIZE, FINAL_SIZE), dtype=np.uint8)
    x_off, y_off = (FINAL_SIZE - new_w) // 2, (FINAL_SIZE - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    return canvas

# ==========================================
# 4. MAIN GENERATOR LOOP
# ==========================================
def generate_frames():
    global system_state, selected_cards

    # Initialize ML Model
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO, num_hands=2)
    landmarker = vision.HandLandmarker.create_from_options(options)

    # Dynamic Camera Management: Opens only 1 camera at a time to preserve USB bus bandwidth
    cap = cv2.VideoCapture(0)
    current_cam_index = 0

    try:
        # FSM State Vars: Gesture
        value_stab, suit_stab, cmd_stab = StableLabel(), StableLabel(), StableLabel()
        armed, hold_counter, cooldown = False, 0, 0
        cmd_was_active = False 
        last_toggle_time = 0.0

        # FSM State Vars: Sorting
        dispenser_state = "WAITING" 
        last_dispense_action = time.time()
        sorter_active = False
        sorter_reset_time = 0.0

        # Debounce tracking dictionary for physical card misfeeds
        accepted_history = {} 

        timestamp_ms = 0

        while True:
            # --- Dynamic Camera Switching ---
            # Ensures the active camera matches the current FSM state
            if system_state == "GESTURE" and current_cam_index != 0:
                cap.release()
                cap = cv2.VideoCapture(0)
                current_cam_index = 0
            elif system_state == "SORTING" and current_cam_index != 1:
                cap.release()
                cap = cv2.VideoCapture(1)
                current_cam_index = 1

            # --------------------------------------------------
            # PHASE 1: GESTURE SELECTION
            # --------------------------------------------------
            if system_state == "GESTURE":
                success, frame = cap.read()
                if not success: continue
                frame = cv2.flip(frame, 1)

                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                timestamp_ms += 33
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                val_raw, suit_raw, cmd_raw = "NONE", "NONE", "NONE"
                if result.hand_landmarks:
                    for hand_landmarks, handedness in zip(result.hand_landmarks, result.handedness):
                        draw_hand(frame, hand_landmarks)
                        # Swap handedness since camera is mirrored
                        lr = "Left" if handedness[0].category_name == "Right" else "Right"
                        if lr == "Left":
                            val_raw = classify_value(hand_landmarks)
                            cmd_raw = classify_command(hand_landmarks)
                        else:
                            suit_raw = classify_suit(hand_landmarks)

                v_stab, s_stab, c_stab = value_stab.update(val_raw), suit_stab.update(suit_raw), cmd_stab.update(cmd_raw)

                # Edge Trigger Toggle Logic (with 1.5s rapid re-arm prevention)
                is_toggle_cmd = (c_stab == "TOGGLE_ARM")
                if is_toggle_cmd and not cmd_was_active and (time.time() - last_toggle_time > 1.5):
                    was_armed = armed
                    armed = not armed
                    last_toggle_time = time.time()
                    hold_counter = 0

                    # STATE TRANSITION: Pivot to SORTING Mode
                    if was_armed and not armed and len(selected_cards) > 0:
                        print("Transitioning to SORTING mode...")
                        system_state = "SORTING"
                        accepted_history.clear() 
                        motor_pwm.ChangeDutyCycle(MOTOR_SPEED)
                        move_servo_to(servo_1_port, SERVO_1_STATE_B) # Lock to Reject
                        move_servo_to(servo_2_port, SERVO_2_RIGHT)   # Pre-cock kicker
                        dispenser_state = "PUSHING"
                        last_dispense_action = time.time()
                        cmd_was_active = is_toggle_cmd
                        continue
                
                cmd_was_active = is_toggle_cmd

                if cooldown > 0: cooldown -= 1
                if armed and v_stab != "NONE" and s_stab != "NONE": hold_counter += 1
                else: hold_counter = 0

                if armed and hold_counter >= 10 and cooldown == 0:
                    pair = (v_stab, s_stab)
                    if not selected_cards or selected_cards[-1] != pair:
                        selected_cards.append(pair)
                    cooldown = 15
                    hold_counter = 0

                # Render Data overlay
                cv2.putText(frame, f"VALUE: {v_stab} | SUIT: {s_stab}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
                cv2.putText(frame, f"ARMED: {armed}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0) if armed else (0,0,255), 2)
                cv2.putText(frame, f"Cards: {selected_cards[-3:]}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

                ret, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            # --------------------------------------------------
            # PHASE 2: DISPENSING & SORTING
            # --------------------------------------------------
            elif system_state == "SORTING":
                success, frame = cap.read()
                if not success: continue

                current_time = time.time()

                # 0. Lifecycle Termination Condition
                if len(selected_cards) == 0 and not sorter_active:
                    print("All targets found! Returning to GESTURE interface.")
                    system_state = "GESTURE"
                    armed = False
                    motor_pwm.ChangeDutyCycle(0) # Cut power to main drive
                    move_servo_to(servo_1_port, SERVO_1_STATE_B) 
                    move_servo_to(servo_2_port, SERVO_2_CENTER)  
                    continue

                # 1. Non-Blocking Dispenser Rhythm (Servo 2)
                # Utilizes time offsets rather than time.sleep() to preserve Flask streaming
                if dispenser_state == "PUSHING" and (current_time - last_dispense_action > 0.5):
                    move_servo_to(servo_2_port, SERVO_2_CENTER)
                    dispenser_state = "WAITING"
                    last_dispense_action = current_time
                elif dispenser_state == "WAITING" and (current_time - last_dispense_action > 0.35):
                    move_servo_to(servo_2_port, SERVO_2_RIGHT)
                    dispenser_state = "PUSHING"
                    last_dispense_action = current_time

                # 2. Asynchronous Sorter Flap Reset (Servo 1)
                # Resets gate to REJECT after 1.5s to ensure physical drop clearance
                if sorter_active and (current_time - sorter_reset_time > 1.5):
                    move_servo_to(servo_1_port, SERVO_1_STATE_B)
                    sorter_active = False

                # 3. Memory Cleanup (Prune stale history entries to prevent dictionary bloat)
                stale_keys = [k for k, t in accepted_history.items() if current_time - t > 3.0]
                for k in stale_keys:
                    del accepted_history[k]

                # 4. Computer Vision Target Matching
                roi = frame[cam1_y:cam1_y+cam1_h, cam1_x:cam1_x+cam1_w]
                live_canvas = preprocess_live_roi(roi)
                cv2.rectangle(frame, (cam1_x, cam1_y), (cam1_x+cam1_w, cam1_y+cam1_h), (0, 255, 0), 2)

                if live_canvas is not None:
                    best_score, best_match = -1.0, "Scanning..."
                    # Execute CCOEFF_NORMED across local dictionary
                    for name, template_img in templates.items():
                        score = cv2.matchTemplate(live_canvas, template_img, cv2.TM_CCOEFF_NORMED)[0][0]
                        if score > best_score:
                            best_score, best_match = score, name

                    if best_score > 0.75:
                        match_tuple = None
                        for v, s in selected_cards:
                            if f"{v}_{s}" == best_match:
                                match_tuple = (v, s)
                                break
                        
                        # --- PHYSICAL DEBOUNCE & MISFEED LOGIC ---
                        if match_tuple:
                            # True Positive: Remove target, log time, route to ACCEPT bin
                            selected_cards.remove(match_tuple)
                            accepted_history[best_match] = current_time
                            move_servo_to(servo_1_port, SERVO_1_STATE_A) 
                            sorter_active = True
                            sorter_reset_time = current_time 
                        elif best_match in accepted_history and (current_time - accepted_history[best_match] < 2.0):
                            # Misfeed Detected: Target card bounced/remained in view. 
                            # Extend the clearance timer instead of reverting to Reject.
                            move_servo_to(servo_1_port, SERVO_1_STATE_A)
                            sorter_active = True
                            sorter_reset_time = current_time
                            accepted_history[best_match] = current_time 
                        else:
                            # Non-target identified
                            move_servo_to(servo_1_port, SERVO_1_STATE_B) 

                        # Render scanning telemetry
                        cv2.rectangle(frame, (cam1_x, cam1_y-30), (cam1_x+cam1_w, cam1_y), (0, 0, 0), -1)
                        cv2.putText(frame, f"{best_match} ({int(best_score*100)}%)", (cam1_x+5, cam1_y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                ret, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    finally:
        # Guarantee hardware release upon web stream termination
        print("Releasing camera resources...")
        if cap is not None:
            cap.release()

# ==========================================
# 5. FLASK ROUTES & CLEANUP
# ==========================================
@app.route('/')
def index():
    return '''<html><body style="background-color: #121212; color: white; text-align: center; font-family: sans-serif;">
              <h2>Magic Robot Stream</h2><img src="/video_feed" style="max-width: 80%; border: 3px solid #333;" /></body></html>'''

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    try:
        print("Starting Master Controller... http://100.105.61.45:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        # Critical physical safety stop to prevent motor overheating
        print("Shutting down hardware safely...")
        motor_pwm.stop()
        GPIO.output(MOTOR_IN1, GPIO.LOW)
        GPIO.cleanup()
        move_servo_to(servo_1_port, SERVO_1_CENTER)
        move_servo_to(servo_2_port, SERVO_2_CENTER)
        time.sleep(0.5)
        pca.deinit()

