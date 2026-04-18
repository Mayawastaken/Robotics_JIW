import cv2
import time

print("Warming up camera...")
cap = cv2.VideoCapture(0)
time.sleep(2)

if not cap.isOpened():
    print("Error: Could not find the Logitech camera.")
else:
    ret, frame = cap.read()
    if ret:
        cv2.imwrite("peephole_test.jpg", frame)
        print("Success! Saved as 'peephole_test.jpg'.")
    else:
        print("Error: Couldn't grab a frame.")

cap.release()
print("Camera turned off.")
