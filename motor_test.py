import time
import RPi.GPIO as GPIO

MOTOR_IN1 = 5
MOTOR_IN2 = 6

print("Starting motor-only test...")

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_IN1, GPIO.OUT)
GPIO.setup(MOTOR_IN2, GPIO.OUT)

try:
    print("Motor forward for 2 seconds...")
    GPIO.output(MOTOR_IN1, GPIO.HIGH)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    time.sleep(2)

    print("Motor off for 2 seconds...")
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    time.sleep(2)

    print("Motor reverse for 2 seconds...")
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.HIGH)
    time.sleep(2)

    print("Motor off.")
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.LOW)

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    GPIO.cleanup()
    print("Clean shutdown complete.")
