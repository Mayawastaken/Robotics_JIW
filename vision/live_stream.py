from flask import Flask, Response
import cv2
import time

app = Flask(__name__)
# 0 is usually the Logitech camera
cap = cv2.VideoCapture(0)
# Let the sensor warm up
time.sleep(2)

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # Encode the frame as a JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            # Yield the frame to the web browser in a continuous stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def video_feed():
    # This route returns the continuous video stream
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print("Starting Live Video Feed...")
    print("Open Chrome and go to: http://100.105.61.45:5000")
    # host='0.0.0.0' allows it to broadcast over your Tailscale network!
    app.run(host='0.0.0.0', port=5000, debug=False)
