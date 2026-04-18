import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque

# CURRENT OOPS, 9 symbol is the same as rock symbol = read in commands gesture
# MAYA !!!!

MODEL_PATH = "models/hand_landmarker.task"

HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (0, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (0, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm connections
    (5, 9), (9, 13), (13, 17)
]

class StableLabel:
    """
    Debounces a stream of labels. Only outputs a label after it appears
    consistently over the last N frames.
    """
    def __init__(self, window=10, min_count=8):
        self.window = window
        self.min_count = min_count
        self.buf = deque(maxlen=window)
        self.locked = "NONE"

    def update(self, label):
        self.buf.append(label)
        # Count most common label in buffer
        counts = {}
        for x in self.buf:
            counts[x] = counts.get(x, 0) + 1
        best = max(counts, key=counts.get)
        if counts[best] >= self.min_count and best != self.locked:
            self.locked = best
        return self.locked
    
def finger_state(hand_landmarks):
    """
    Returns a dict of which fingers are extended.
    For now assumes palm roughly facing camera.
    """
    def y(i): return hand_landmarks[i].y
    def x(i): return hand_landmarks[i].x

    # Non-thumb: tip above PIP => extended (y decreases upward)
    index_up  = y(8)  < y(6)
    middle_up = y(12) < y(10)
    ring_up   = y(16) < y(14)
    pinky_up  = y(20) < y(18)

    # Thumb: use x direction relative to thumb IP joint as a crude heuristic.
    # This is imperfect but okay for MVP.
    # For a right hand facing camera, thumb tip tends to be left of IP; for left hand it can invert.
    # We'll avoid relying on thumb for suit gestures to keep things robust.
    thumb_up = abs(x(4) - x(2)) > 0.04  # “thumb is out” vs tucked-ish

    return {
        "thumb": thumb_up,
        "index": index_up,
        "middle": middle_up,
        "ring": ring_up,
        "pinky": pinky_up,
    }

def classify_suit(hand_landmarks):
    def y(i): 
        return hand_landmarks[i].y

    # For these 4 fingers: tip above pip => finger extended (image y axis points down)
    index_up  = y(8)  < y(6)
    middle_up = y(12) < y(10)
    ring_up   = y(16) < y(14)
    pinky_up  = y(20) < y(18)

    up = [index_up, middle_up, ring_up, pinky_up]
    count_up = sum(up)

    if count_up == 4: # open palm or all fingers up
        return "HEARTS"
    if index_up and middle_up and ring_up and not pinky_up: # holding up 3 (with or without thumb) looks a bit like spade shape
        return "SPADES"
    if index_up and not (middle_up or ring_up or pinky_up): # index only
        return "CLUBS"
    if pinky_up and not (index_up or middle_up or ring_up): # pinky only
        return "DIAMONDS"
    return "NONE"

VALUE_MAP = {
    1: "A", 2: "2", 3: "3", 4: "4", 5: "5",
    6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K",
}
VALID_VALUES = set(VALUE_MAP.values())  # {"A","2",...,"K"}

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
    i, m, r, p = fs["index"], fs["middle"], fs["ring"], fs["pinky"]

    # "rock" gesture: index + pinky only
    if i and p and (not m) and (not r):
        return "TOGGLE_ARM"
    return "NONE"
    
def extract_handedness(result):
    """
    Returns a list like ['Left', 'Right'] aligned with result.hand_landmarks.
    """
    labels = []
    for h in result.handedness:
        # h is a list of Category objects
        labels.append(h[0].category_name)
    return labels

def draw_hand(frame, hand_landmarks, line_color=(0, 255, 0), dot_color=(0, 0, 255)):
    h, w, _ = frame.shape
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]

    # Lines (skeleton)
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], line_color, 2)

    # Dots (joints)
    for (x, y) in pts:
        cv2.circle(frame, (x, y), 3, dot_color, -1)

def classify_gesture(hand_landmarks):
    """
    MVP gesture classifier using which fingers are extended.
    Returns: 'OPEN_PALM', 'FIST', 'POINT', or 'NONE' (unknown)
    Works best for a hand facing the camera.
    """
    def y(i): 
        return hand_landmarks[i].y

    # For these 4 fingers: tip above pip => finger extended (image y axis points down)
    index_up  = y(8)  < y(6)
    middle_up = y(12) < y(10)
    ring_up   = y(16) < y(14)
    pinky_up  = y(20) < y(18)

    up = [index_up, middle_up, ring_up, pinky_up]
    count_up = sum(up)

    if count_up == 4:
        return "OPEN_PALM"
    if count_up == 0:
        return "FIST"
    if index_up and not (middle_up or ring_up or pinky_up):
        return "POINT"
    return "NONE"

def avg_x(hand_landmarks):
    return sum(lm.x for lm in hand_landmarks) / len(hand_landmarks)


VALID_VALUES = set(["A","2","3","4","5","6","7","8","9","10","J","Q","K"])
VALID_SUITS  = set(["HEARTS","SPADES","DIAMONDS","CLUBS"])

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2, # enable two hand detection
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    timestamp_ms = 0
    value_stab = StableLabel()
    suit_stab  = StableLabel()
    cmd_stab  = StableLabel()

    armed = False
    selected = []   # list of (value, suit)
    hold_counter = 0
    cooldown = 0
    toggle_cooldown = 0
    HOLD_FRAMES = 20     # ~0.6s at 30fps; adjust
    COOLDOWN_FRAMES = 25 # ~0.8s cooldown (i think) after selection; adjust as needed
    TOGGLE_COOLDOWN_FRAMES = 300 # cooldown for toggle command to avoid rapid toggling

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)  # selfie view
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        timestamp_ms += 33
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        value_raw = "NONE"
        suit_raw  = "NONE"
        cmd_raw   = "NONE"

        hands = result.hand_landmarks or []

        # Draw all hands
        for hand_landmarks in hands:
            draw_hand(frame, hand_landmarks,
                      line_color=(0,255,0),
                      dot_color=(0,0,255))

        if hands:
            labels = extract_handedness(result)

            # IMPORTANT:
            # Because we flipped the image, handedness is often reversed.
            # If VALUE/SUIT feel swapped, uncomment the next line.
            labels = ["Left" if x == "Right" else "Right" for x in labels]

            for hand_landmarks, lr in zip(hands, labels):
                if lr == "Left":
                    value_raw = classify_value(hand_landmarks)
                    cmd_raw   = classify_command(hand_landmarks) # left hand must be used to activate hand reading
                elif lr == "Right":
                    suit_raw = classify_suit(hand_landmarks)

        value_stable = value_stab.update(value_raw)
        suit_stable  = suit_stab.update(suit_raw)
        cmd_stable = cmd_stab.update(cmd_raw)

        if cmd_stable == "TOGGLE_ARM" and toggle_cooldown == 0:
            armed = not armed
            cooldown = COOLDOWN_FRAMES  
            toggle_cooldown = TOGGLE_COOLDOWN_FRAMES
        
        if cooldown > 0:
            cooldown -= 1

        if toggle_cooldown > 0:
            toggle_cooldown -= 1

        if armed and value_stable != "NONE" and suit_stable != "NONE":
            hold_counter += 1
        else:
            hold_counter = 0

        if armed and hold_counter >= HOLD_FRAMES and cooldown == 0:
            pair = (value_stable, suit_stable)
            # avoid duplicates back-to-back; technically doesn't avoid duplicates ever 
            # but I'll recall not to ask for / signal duplicate cards
            # if value_stable in VALID_VALUES and suit_stable in VALID_SUITS:
            if not selected or selected[-1] != pair:
                selected.append(pair)
            cooldown = COOLDOWN_FRAMES
            hold_counter = 0


        cv2.putText(frame, f"VALUE (Left):  {value_stable}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2) #open CV is BGR
        cv2.putText(frame, f"SUIT  (Right): {suit_stable}", (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        cv2.putText(frame, f"ARMED: {armed}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0) if armed else (0,0,255), 2)
        cv2.putText(frame, f"Selected: {selected[-3:]}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)


        cv2.imshow("Hand Landmarker (Tasks)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
