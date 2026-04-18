import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = "models/hand_landmarker.task"

def main():
    cap = cv2.VideoCapture(0)  # try 1 if needed
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Try VideoCapture(1) or check permissions/Zoom.")

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    timestamp_ms = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Timestamp must be monotonically increasing for VIDEO mode
        timestamp_ms += 33  # ~30 FPS; fine for a prototype
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        # Draw landmarks
        if result.hand_landmarks:
            h, w, _ = frame.shape
            for hand in result.hand_landmarks:
                for lm in hand:
                    x, y = int(lm.x * w), int(lm.y * h)
                    cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

        cv2.imshow("Hand Landmarker (Tasks)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

# import cv2
# import mediapipe as mp
# from mediapipe.tasks import python
# from mediapipe.tasks.python import vision

# MODEL_PATH = "models/hand_landmarker.task"  # update if you name it differently

# def main():
#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         raise RuntimeError("Could not open webcam. Try VideoCapture(1) or check permissions.")

#     base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
#     options = vision.HandLandmarkerOptions(
#         base_options=base_options,
#         num_hands=1
#     )
#     detector = vision.HandLandmarker.create_from_options(options)

#     while True:
#         ok, frame = cap.read()
#         if not ok:
#             break

#         frame = cv2.flip(frame, 1)
#         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

#         mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
#         result = detector.detect(mp_image)

#         # Draw landmarks if present
#         if result.hand_landmarks:
#             h, w, _ = frame.shape
#             for hand in result.hand_landmarks:
#                 for lm in hand:
#                     x, y = int(lm.x * w), int(lm.y * h)
#                     cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

#         cv2.imshow("MediaPipe Tasks - Hand Landmarks", frame)
#         key = cv2.waitKey(1) & 0xFF
#         if key == 27 or key == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()

# import cv2
# import mediapipe as mp
# import time

# def main():
#     cap = cv2.VideoCapture(0)  # try 1 if 0 doesn't work
#     if not cap.isOpened():
#         raise RuntimeError("Could not open webcam. Try VideoCapture(1) or check camera permissions.")

#     mp_hands = mp.solutions.hands
#     mp_draw = mp.solutions.drawing_utils

#     # Start with moderate settings; we can tune later for Pi
#     hands = mp_hands.Hands(
#         static_image_mode=False,
#         max_num_hands=1,
#         model_complexity=1,
#         min_detection_confidence=0.6,
#         min_tracking_confidence=0.6,
#     )

#     prev_t = time.time()

#     while True:
#         ok, frame = cap.read()
#         if not ok:
#             break

#         frame = cv2.flip(frame, 1)  # mirror for natural interaction
#         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

#         result = hands.process(rgb)

#         if result.multi_hand_landmarks:
#             for hand_landmarks in result.multi_hand_landmarks:
#                 mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

#         # FPS display (helps later when moving to Pi)
#         t = time.time()
#         fps = 1.0 / (t - prev_t)
#         prev_t = t
#         cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
#                     cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

#         cv2.imshow("Hand Landmarks", frame)
#         key = cv2.waitKey(1) & 0xFF
#         if key == 27 or key == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()