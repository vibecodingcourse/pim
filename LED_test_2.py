from gpiozero import Button, LED
from signal import pause

button = Button(17, pull_up=True, bounce_time=0.1)
led = LED(18)

# Track LED state
led_on = False

def toggle_led():
    global led_on
    led_on = not led_on
    if led_on:
        print("💡 LED ON")
        led.on()
    else:
        print("🌑 LED OFF")
        led.off()

button.when_pressed = toggle_led

print("📥 Press button to toggle LED (Ctrl+C to exit)")
pause()