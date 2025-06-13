import RPi.GPIO as GPIO
import time

# ===== SETUP =====
BUTTON_PIN = 17  # GPIO 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("🔘 Waiting for button press on GPIO 17... (Press Ctrl+C to stop)")

# ===== LOOP =====
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            print("✅ Button pressed!")
            time.sleep(0.3)  # debounce
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\n👋 Exiting...")
finally:
    GPIO.cleanup()