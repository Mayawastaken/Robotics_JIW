import time
import board
import busio
from adafruit_pca9685 import PCA9685

SERVO_MIN = 150
SERVO_MAX = 600
SERVO_FREQ = 50

SERVO_1_PORT = 0
SERVO_2_PORT = 1

CENTER = 90
RIGHT = 20

def angle_to_duty(angle):
    pulse_length = SERVO_MIN + (angle / 180.0) * (SERVO_MAX - SERVO_MIN)
    duty_cycle = int((pulse_length / 4096.0) * 65535)
    return duty_cycle

def move_servo_to(pca, port, degrees):
    pca.channels[port].duty_cycle = angle_to_duty(degrees)

print("Starting servo-only test...")

i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = SERVO_FREQ

try:
    move_servo_to(pca, SERVO_1_PORT, CENTER)
    move_servo_to(pca, SERVO_2_PORT, CENTER)
    time.sleep(1)

    while True:
        print("Moving servo 1")
        move_servo_to(pca, SERVO_1_PORT, RIGHT)
        time.sleep(0.5)
        move_servo_to(pca, SERVO_1_PORT, CENTER)
        time.sleep(0.5)

        print("Moving servo 2")
        move_servo_to(pca, SERVO_2_PORT, RIGHT)
        time.sleep(0.5)
        move_servo_to(pca, SERVO_2_PORT, CENTER)
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    print("Centering servos and cleaning up...")
    try:
        move_servo_to(pca, SERVO_1_PORT, CENTER)
        move_servo_to(pca, SERVO_2_PORT, CENTER)
        time.sleep(0.5)
    except Exception:
        pass

    pca.deinit()
    print("Done.")
