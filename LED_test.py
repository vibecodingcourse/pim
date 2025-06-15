from gpiozero import Button, LED
from signal import pause

# GPIO pin assignments
button = Button(17, pull_up=True)  # Physical pin 11
led = LED(18)                      # Physical pin 12

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