import time
import board
import busio
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685

# ---------------------------------------------
# Hardware Constants & Settings
# ---------------------------------------------
# PWM Pulse constraints (Matches Arduino)
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

# Timing (Seconds)
sweep_time = 0.5   
offbeat_wait = 0.35

# ---------------------------------------------
# Setup Hardware
# ---------------------------------------------
print("Starting Dual-Servo + Gear Motor Test...")

# 1. Setup the Gear Motor Pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) 
GPIO.setup(MOTOR_IN1, GPIO.OUT)
GPIO.setup(MOTOR_IN2, GPIO.OUT)

# Turn the gear motor ON (Forward)
time.sleep(2)
GPIO.output(MOTOR_IN1, GPIO.HIGH)
GPIO.output(MOTOR_IN2, GPIO.LOW)

# 2. Setup the Servos (I2C Bridge)
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = SERVO_FREQ

# --- Helper Function ---
def move_servo_to(port, degrees):
    # Using the constants to map the angle to the pulse length
    pulse_length = SERVO_MIN + (degrees / 180.0) * (SERVO_MAX - SERVO_MIN)
    # Convert 12-bit pulse length to 16-bit duty cycle for Adafruit library
    duty_cycle = int((pulse_length / 4096.0) * 65535)
    pca.channels[port].duty_cycle = duty_cycle

# Snap to center at startup
move_servo_to(servo_1_port, CENTER)
move_servo_to(servo_2_port, CENTER)
time.sleep(1)

# ---------------------------------------------
# The Main Loop
# ---------------------------------------------
try:
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
    print("\nTest Stopped by user (Ctrl+C).")

finally:
    # This block ALWAYS runs, even if the script crashes!
    print("Shutting down motors safely...")
    
    # 1. Neatly center the servos and give them time to move there
    move_servo_to(servo_1_port, CENTER)
    move_servo_to(servo_2_port, CENTER)
    time.sleep(0.5) 
    
    # 2. Explicitly kill power to the gear motor driver
    GPIO.output(MOTOR_IN1, GPIO.LOW)
    GPIO.output(MOTOR_IN2, GPIO.LOW)
    
    # 3. Cleanly disconnect from the hardware
    GPIO.cleanup()
    pca.deinit()
    print("System offline. Safe to unplug.")


# import time
# import board
# import busio
# import RPi.GPIO as GPIO
# from adafruit_pca9685 import PCA9685

# # --- Gear Motor Logic Pins ---
# MOTOR_IN1 = 5
# MOTOR_IN2 = 6

# # --- Servo Ports ---
# servo1Port = 0
# servo2Port = 1

# # Standard angles
# CENTER = 90
# RIGHT = 20

# # Timing (Seconds)
# sweepTime = 0.5   
# offbeatWait = 0.35

# # ---------------------------------------------
# # Setup Hardware
# # ---------------------------------------------
# print("Starting Dual-Servo + Gear Motor Test...")

# # 1. Setup the Gear Motor Pins
# GPIO.setwarnings(False)
# GPIO.setmode(GPIO.BCM) 
# GPIO.setup(MOTOR_IN1, GPIO.OUT)
# GPIO.setup(MOTOR_IN2, GPIO.OUT)

# # Turn the gear motor ON (Forward)
# # To reverse direction, swap HIGH and LOW here
# GPIO.output(MOTOR_IN1, GPIO.HIGH)
# GPIO.output(MOTOR_IN2, GPIO.LOW)

# # 2. Setup the Servos (I2C Bridge)
# i2c = busio.I2C(board.SCL, board.SDA)
# pca = PCA9685(i2c)
# pca.frequency = 50

# # Helper Function
# def moveServoTo(port, degrees):
#     pulseLength = 150 + (degrees / 180.0) * (600 - 150)
#     duty_cycle = int((pulseLength / 4096.0) * 65535)
#     pca.channels[port].duty_cycle = duty_cycle

# # Snap to center at startup
# moveServoTo(servo1Port, CENTER)
# moveServoTo(servo2Port, CENTER)
# time.sleep(1)

# # ---------------------------------------------
# # The Main Loop
# # ---------------------------------------------
# try:
#     while True:
#         # BEAT 1: SERVO 1
#         moveServoTo(servo1Port, RIGHT)
#         time.sleep(sweepTime)
#         moveServoTo(servo1Port, CENTER)
        
#         time.sleep(offbeatWait)

#         # OFFBEAT: SERVO 2
#         moveServoTo(servo2Port, RIGHT)
#         time.sleep(sweepTime)
#         moveServoTo(servo2Port, CENTER)
        
#         time.sleep(offbeatWait)

# except KeyboardInterrupt:
#     print("\nTest Stopped. Shutting down motors...")
#     GPIO.cleanup()
#     pca.deinit()
