import platform
import sys

IS_RASPBERRY = platform.machine().startswith("arm") and "raspberrypi" in platform.uname().nodename

if IS_RASPBERRY:
    import RPi.GPIO as GPIO #pip install python3-rpi.gpio
else:
    import keyboard  #pip install keyboard

BEAM_PIN = 17
SIMULATED_KEY = "space"
beam_status = False

def beam_broken():
    if IS_RASPBERRY:
        return GPIO.input(BEAM_PIN) == 0
    else:
        return keyboard.is_pressed(SIMULATED_KEY)

def break_beam_callback():
    global beam_status
    _beam_status = beam_broken()
    
    if _beam_status != beam_status:
        if _beam_status:
            print("Beam broken")
        else:
            print("Beam unbroken")
    
    beam_status = _beam_status

try:
    if IS_RASPBERRY:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BEAM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(BEAM_PIN, GPIO.BOTH, callback=lambda x: break_beam_callback())
        print("Running on Raspberry Pi. Press Ctrl+C to exit.")
    else:
        print(f"Running on PC. Press '{SIMULATED_KEY}' to simulate sensor break. Press Ctrl+C to exit.")

    # Bucle principal
    while True:
        if not IS_RASPBERRY:
            break_beam_callback()
        pass

except KeyboardInterrupt:
    print("\nExiting program.")

finally:
    if IS_RASPBERRY:
        GPIO.cleanup()
    else:
        print("Program ended.")