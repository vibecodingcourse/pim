from gpiozero import Button, LED
import threading
import time
import atexit
import RPi.GPIO as GPIO

button = Button(17, pull_up=True, bounce_time=0.1)
led = LED(18)
state = "idle"
running = True

def set_state(new_state):
    global state
    state = new_state
    print(f"🔁 State: {state}")

def led_loop():
    global state
    while running:
        if state == "idle":
            led.off(); time.sleep(5); led.on(); time.sleep(0.1); led.off()
        elif state == "ready":
            led.on(); time.sleep(0.2)
        elif state == "listening":
            led.toggle(); time.sleep(0.1)
        elif state == "processing":
            led.toggle(); time.sleep(0.5)
        elif state == "speaking":
            for _ in range(3): led.on(); time.sleep(0.1); led.off(); time.sleep(0.1)
            state = "ready"
        else:
            led.off(); time.sleep(0.1)

def start_led_thread():
    threading.Thread(target=led_loop, daemon=True).start()

def cleanup_gpio():
    GPIO.cleanup()

atexit.register(cleanup_gpio)