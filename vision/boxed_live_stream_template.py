from flask import Flask, Response
import cv2
import time

app = Flask(__name__)

print("Warming up camera...")
cap = cv2.VideoCapture(0)
time.sleep(2)

# Global variable to hold the clean, box-free frame
current_frame = None

# --- YOUR TIGHTENED ROI NUMBERS ---
# (Update these if you changed them earlier!)
#x = 285  #260 # 265 MOST RECENT
#y = 248  # or maybe 260
#w = 195  #232 # 227 MOST RECENT FOR SIG   
#h = 82 # or maybe 82 | 136 for ratio 17 to 29 # 89 MOST  RECENT FOR SIG  
x = 280
y = 239
w = 193
h = 98

def generate_frames():
    global current_frame
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # Save a clean copy of the frame BEFORE we draw the green box
            current_frame = frame.copy()
            
            # Make a copy for the stream and draw the green box on it
            stream_frame = frame.copy()
            cv2.rectangle(stream_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Broadcast the green-box version to the browser
            ret, buffer = cv2.imencode('.jpg', stream_frame)
            final_frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + final_frame + b'\r\n')

@app.route('/')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- THE REMOTE SHUTTER BUTTON ---
@app.route('/snap/<card_name>')
def snap(card_name):
    global current_frame
    if current_frame is not None:
        # Crop the CLEAN frame (no green lines!)
        cropped_roi = current_frame[y:y+h, x:x+w]
        
        # Save it using the name you typed in the URL
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
