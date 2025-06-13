import RPi.GPIO as GPIO
import time

PIN = 17  # BCM GPIO 17 = physical pin 11

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("🔘 Press the button connected to GPIO 17 (pin 11). Press Ctrl+C to exit.")

try:
    while True:
        if GPIO.input(PIN) == GPIO.LOW:
            print("✅ Button pressed!")
            time.sleep(0.3)  # debounce
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\n👋 Exiting...")
finally:
    GPIO.cleanup()