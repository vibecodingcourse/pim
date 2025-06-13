from gpiozero import Button
from signal import pause

# Use GPIO 17 (physical pin 11)
button = Button(17, pull_up=True)

def on_press():
    print("✅ Button pressed!")

button.when_pressed = on_press

print("📥 Waiting for button press (Ctrl+C to exit)")
pause()