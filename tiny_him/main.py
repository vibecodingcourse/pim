from platform_utils import detect_pi_model, is_online, detect_microphone, detect_speaker
from openai import OpenAI
from gpio_handler import start_led_thread, set_state
from interaction import run_interaction
import config
import threading
import time
import sys
import os

from gpiozero import Button
from signal import pause
import atexit
import RPi.GPIO as GPIO

os.environ["OPENAI_API_KEY"] = open("part1.txt").read().strip() + open("part2.txt").read().strip()
client = OpenAI()

# Set flags
pi_model = detect_pi_model()
online = is_online()
USE_LOCAL = (pi_model == "Pi 5" and not online)

whisper_model = None
if USE_LOCAL:
    import whisper
    whisper_model = whisper.load_model(config.MODEL_SIZE)

has_mic = detect_microphone()
has_speaker = detect_speaker()

interaction_lock = threading.Lock()
stop_event = threading.Event()

def button_handler():
    from gpio_handler import button
    while True:
        button.wait_for_press()
        if not interaction_lock.acquire(blocking=False):
            continue
        stop_event.clear()
        threading.Thread(target=wrapped_interaction, daemon=True).start()
        time.sleep(0.3)

def wrapped_interaction():
    try:
        run_interaction(client, config, stop_event, whisper_model, online=not USE_LOCAL)
    finally:
        interaction_lock.release()

set_state("ready")
start_led_thread()
threading.Thread(target=button_handler, daemon=True).start()

try:
    pause()
except KeyboardInterrupt:
    print("\n👋 Exiting...")
finally:
    GPIO.cleanup()