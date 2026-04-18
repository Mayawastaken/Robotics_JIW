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
servo_1_port = 0  # Column 0 (The Dispenser Flap)
servo_2_port = 1  # Column 1 (The Sorter)

# --- THE CENTER LOGIC ---
SERVO_1_CENTER = 99  # Nudged left by half a tooth to fix right-tilt
SERVO_2_CENTER = 90  # Keep servo 2 perfectly standard

# --- THE ALTERNATING STATES FOR COL 0 ---
# State A: -25 degrees from center (74 degrees)
# State B: +22 degrees from center (121 degrees)
SERVO_1_STATE_A = SERVO_1_CENTER - 29
SERVO_1_STATE_B = SERVO_1_CENTER + 27

# Sorter Target
SERVO_2_RIGHT = 5    # leave unchanged

# Timing (seconds) - Kept the same to maintain the machine's rhythm
sweep_time = 0.5
offbeat_wait = 0.35

# Motor speed (0 to 100)
MOTOR_SPEED = 70 # was 45. trying 55

# ---------------------------------------------
# Setup Hardware
# ---------------------------------------------
print("Starting Mixed Test: Alternating Col 0 every 5 sweeps...")

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

    # Snap to their respective centers at startup
    move_servo_to(servo_1_port, SERVO_1_CENTER)
    move_servo_to(servo_2_port, SERVO_2_CENTER)
    time.sleep(1)

    # ---------------------------------------------
    # The Action Loop
    # ---------------------------------------------
    
    sweep_counter = 0

    print("Running sequence. Press Ctrl+C to stop.")

    while True:
        # Determine which state Servo 1 should hold based on the counter
        # Integer division (//) flips the output 0 or 1 every 5 loops
        if (sweep_counter // 5) % 2 == 0:
            current_col_0_target = SERVO_1_STATE_A  # -25 degrees
            print(f"Block [{sweep_counter//5}]: Setting Dispenser to {current_col_0_target} deg")
        else:
            current_col_0_target = SERVO_1_STATE_B  # +22 degrees
            print(f"Block [{sweep_counter//5}]: Setting Dispenser to {current_col_0_target} deg")

        # 1. Lock/Update Column 0 (Dispenser)
        move_servo_to(servo_1_port, current_col_0_target)

        # Simulate the time it USED to take for Column 0 to sweep back and forth
        time.sleep(sweep_time)
        time.sleep(offbeat_wait)

        # 2. SERVO 2 (Sorter on Column 1) - Quick Flick Motion
        move_servo_to(servo_2_port, SERVO_2_RIGHT)
        time.sleep(sweep_time)
        move_servo_to(servo_2_port, SERVO_2_CENTER) # Returns to its own center

        time.sleep(offbeat_wait)
        
        # Increment our tally of Sorter sweeps
        sweep_counter += 1

except KeyboardInterrupt:
    print("\nTest stopped by user (Ctrl+C).")

finally:
    print("Shutting down motors safely...")

    if pca is not None:
        try:
            # Shut down Servo 1 at its custom center
            move_servo_to(servo_1_port, SERVO_1_CENTER)
            move_servo_to(servo_2_port, SERVO_2_CENTER)
            time.sleep(0.5)

            pulse_length_1 = SERVO_MIN + (SERVO_1_CENTER / 180.0) * (SERVO_MAX - SERVO_MIN)
            duty_cycle_1 = int((pulse_length_1 / 4096.0) * 65535)
            pca.channels[servo_1_port].duty_cycle = duty_cycle_1

            # Shut down Servo 2 at its standard center
            pulse_length_2 = SERVO_MIN + (SERVO_2_CENTER / 180.0) * (SERVO_MAX - SERVO_MIN)
            duty_cycle_2 = int((pulse_length_2 / 4096.0) * 65535)
            pca.channels[servo_2_port].duty_cycle = duty_cycle_2

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
