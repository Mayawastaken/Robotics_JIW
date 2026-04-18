import time
import board
import busio
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685

# ---------------------------------------------
# Hardware Constants & Settings
# ---------------------------------------------
SERVO_MIN = 150
SERVO_MAX = 600
SERVO_FREQ = 50

# Gear Motor Logic Pins (BCM numbering)
MOTOR_IN1 = 5
MOTOR_IN2 = 6

# Servo Ports on the PCA9685
servo_1_port = 0
servo_2_port = 1

# Standard angles
CENTER = 90
SERVO_1_RIGHT = 40   # 30 degrees Right (90 - 30)
SERVO_1_LEFT = 140   # 30 degrees Left  (90 + 30)
SERVO_2_RIGHT = 5    # leave unchanged

# Timing (seconds)
sweep_time = 0.5
offbeat_wait = 0.35

# Motor speed (0 to 100)
MOTOR_SPEED = 45

# ---------------------------------------------
# Setup Hardware
# ---------------------------------------------
print("Starting Dual-Servo + Gear Motor Test...")

pca = None
motor_pwm = None

try:
    # 1. Setup the Gear Motor Pins
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MOTOR_IN1, GPIO.OUT)
    GPIO.setup(MOTOR_IN2, GPIO.OUT)

    # Reverse direction + PWM speed control
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    motor_pwm = GPIO.PWM(MOTOR_IN2, 1000)
    time.sleep(2)
    motor_pwm.start(MOTOR_SPEED)

    # 2. Setup the Servos (I2C Bridge)
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c)
    pca.frequency = SERVO_FREQ

    # --- Helper Function ---
    def move_servo_to(port, degrees):
        pulse_length = SERVO_MIN + (degrees / 180.0) * (SERVO_MAX - SERVO_MIN)
        duty_cycle = int((pulse_length / 4096.0) * 65535)
        pca.channels[port].duty_cycle = duty_cycle

    # Snap to center at startup
    move_servo_to(servo_1_port, CENTER)
    move_servo_to(servo_2_port, CENTER)
    time.sleep(1)

    # ---------------------------------------------
    # The Main Loop
    # ---------------------------------------------
    
    # This acts as our toggle switch memory
    sweep_right_next = True 

    while True:
        # SERVO 1 (Dispenser) - Alternating Wiper Motion
        if sweep_right_next:
            move_servo_to(servo_1_port, SERVO_1_RIGHT)
        else:
            move_servo_to(servo_1_port, SERVO_1_LEFT)
            
        # Flip the toggle so it goes the other way next loop
        sweep_right_next = not sweep_right_next 

        time.sleep(sweep_time)
        time.sleep(offbeat_wait)

        # SERVO 2 (Sorter) - Quick Flick Motion
        move_servo_to(servo_2_port, SERVO_2_RIGHT)
        time.sleep(sweep_time)
        move_servo_to(servo_2_port, CENTER)

        time.sleep(offbeat_wait)

except KeyboardInterrupt:
    print("\nTest stopped by user (Ctrl+C).")

finally:
    print("Shutting down motors safely...")

    if pca is not None:
        try:
            pulse_length = SERVO_MIN + (CENTER / 180.0) * (SERVO_MAX - SERVO_MIN)
            duty_cycle = int((pulse_length / 4096.0) * 65535)
            pca.channels[servo_1_port].duty_cycle = duty_cycle
            pca.channels[servo_2_port].duty_cycle = duty_cycle
            time.sleep(0.5)
        except Exception:
            pass

    if motor_pwm is not None:
        try:
            motor_pwm.stop()
        except Exception:
            pass

    try:
        GPIO.output(MOTOR_IN1, GPIO.LOW)
        GPIO.output(MOTOR_IN2, GPIO.LOW)
    except Exception:
        pass

    try:
        GPIO.cleanup()
    except Exception:
        pass

    if pca is not None:
        try:
            pca.deinit()
        except Exception:
            pass

    print("System offline. Safe to unplug.")
