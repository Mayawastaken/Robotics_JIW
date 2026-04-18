import cv2
import time

print("Warming up camera...")
cap = cv2.VideoCapture(0)
time.sleep(2)

if not cap.isOpened():
    print("Error: Could not access the camera.")
else:
    # Read one frame
    ret, frame = cap.read()
    
    if ret:
        # --- YOUR TIGHTENED ROI NUMBERS ---
        x = 380  
        y = 50  
        w = 232  
        h = 136  
        
        # This is the magic line. It crops the massive frame down to JUST the box.
        # Notice it is [y:y+h, x:x+w] (height comes first in image arrays!)
        cropped_roi = frame[y:y+h, x:x+w]
        
        # Save just the cropped box
        cv2.imwrite("template_ace.jpg", cropped_roi)
        print("Success! 'template_ace.jpg' has been added to your dictionary.")
    else:
        print("Error: Couldn't grab a frame.")

cap.release()
