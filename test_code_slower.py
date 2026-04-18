import time
import board
import busio
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685

# ---------------------------------------------
# Hardware Constants & Settings
# ---------------------------------------------
# PWM Pulse constraints (matches Arduino-ish values)
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
RIGHT = 20

# Timing (seconds)
sweep_time = 0.5
offbeat_wait = 0.35

# Motor speed (0 to 100)
MOTOR_SPEED = 30   # try 30 first; if too slow, bump to 50 or 60

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

    # Opposite direction + PWM speed control
    # Before: IN1 HIGH, IN2 LOW
    # Now reverse: IN1 LOW, IN2 PWM
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    motor_pwm = GPIO.PWM(MOTOR_IN2, 1000)   # 1000 Hz PWM
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
    while True:
        # BEAT 1: SERVO 1
        move_servo_to(servo_1_port, RIGHT)
        time.sleep(sweep_time)
        move_servo_to(servo_1_port, CENTER)

        time.sleep(offbeat_wait)

        # OFFBEAT: SERVO 2
        move_servo_to(servo_2_port, RIGHT)
        time.sleep(sweep_time)
        move_servo_to(servo_2_port, CENTER)

        time.sleep(offbeat_wait)

except KeyboardInterrupt:
    print("\nTest stopped by user (Ctrl+C).")

finally:
    print("Shutting down motors safely...")

    # Center servos if PCA initialized
    if pca is not None:
        try:
            pulse_length = SERVO_MIN + (CENTER / 180.0) * (SERVO_MAX - SERVO_MIN)
            duty_cycle = int((pulse_length / 4096.0) * 65535)
            pca.channels[servo_1_port].duty_cycle = duty_cycle
            pca.channels[servo_2_port].duty_cycle = duty_cycle
            time.sleep(0.5)
        except Exception:
            pass

    # Stop gear motor if PWM initialized
    if motor_pwm is not None:
        try:
            motor_pwm.stop()
        except Exception:
            pass

    # Set both motor inputs low
    try:
        GPIO.output(MOTOR_IN1, GPIO.LOW)
        GPIO.output(MOTOR_IN2, GPIO.LOW)
    except Exception:
        pass

    # Clean shutdown
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
