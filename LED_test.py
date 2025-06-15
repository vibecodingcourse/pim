from gpiozero import Button, LED
from signal import pause

# Set bounce_time in seconds (e.g., 0.1 = 100ms)
button = Button(17, pull_up=True, bounce_time=0.1)
led = LED(18)

def on_press():
    print("✅ Button pressed!")
    led.on()

def on_release():
    print("⬜ Button released")
    led.off()

button.when_pressed = on_press
button.when_released = on_release

print("📥 Waiting for button press (Ctrl+C to exit)")
pause()