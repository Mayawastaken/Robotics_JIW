from flask import Flask, Response
import cv2
import time

app = Flask(__name__)

print("Warming up camera...")
# 0 is usually the Logitech camera
cap = cv2.VideoCapture(0)

# Give the camera sensor 2 seconds to adjust to the lighting
time.sleep(2)

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # --- ROI CALIBRATION (THE TARGETING BOX) ---
            # x, y = top left corner coordinates
            # w, h = width and height of the box
            # These are starting numbers; you will need to adjust them!
	    # ratio set to approx 29:17, in upper rightish
            x = 380  
            y = 50  
            w = 232  
            h = 136  

            # Draw a bright green rectangle on the frame
            # Format: cv2.rectangle(image, start_point, end_point, color_bgr, thickness)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            # -------------------------------------------

            # Encode the frame as a JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            stream_frame = buffer.tobytes()
            
            # Yield the frame to the web browser in a continuous stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + stream_frame + b'\r\n')

@app.route('/')
def video_feed():
    # This route returns the continuous video stream
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print("Starting Boxed Live Video Feed...")
    print("Open Chrome and go to: http://100.105.61.45:5000")
    # host='0.0.0.0' broadcasts it over your Tailscale network
    app.run(host='0.0.0.0', port=5000, debug=False)
