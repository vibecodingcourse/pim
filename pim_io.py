import whisper
from gtts import gTTS
import uuid
import subprocess
import threading
import queue
import sys
import platform
import os
import re
import socket
from openai import OpenAI
from gpiozero import Button, LED
from signal import pause
import time
import atexit
import RPi.GPIO as GPIO

sys.path.append('/usr/lib/python3/dist-packages')

# ========== CONFIG ==========

AUDIO_INPUT_PATH = "input.wav"
MODEL_SIZE = "base"
OPENAI_MODEL = "gpt-4.1"
LOCAL_LLM_PATH = "phi-2.Q4_K_M.gguf"
SYSTEM_PROMPT = "You are kind helper like dobbie in Harry Potter. Always answer concisely in English:\n"
IS_MAC = platform.system() == "Darwin"

USE_LOCAL_STT = False
USE_LOCAL_LLM = False
USE_LOCAL_TTS = False

interaction_lock = threading.Lock()
stop_event = threading.Event()

# ========== FORCE GPIO CLEANUP BEFORE USE ==========

def force_gpio_release(pins=[17, 18]):
    for pin in pins:
        try:
            with open("/sys/class/gpio/unexport", "w") as f:
                f.write(str(pin))
            print(f"✅ Released GPIO pin {pin}")
        except Exception:
            pass

force_gpio_release([17, 18])

# ========== GPIO SETUP ==========

button = Button(17, pull_up=True, bounce_time=0.1)
led = LED(18)
atexit.register(GPIO.cleanup)

state = "idle"
running = True

# ========== LED LOOP ==========

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

def set_state(new_state):
    global state
    state = new_state
    print(f"🔁 State: {state}")

threading.Thread(target=led_loop, daemon=True).start()

# ========== UTILITY FUNCTIONS ==========

def is_online(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

def detect_pi_model():
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            model_match = re.search(r"Model\s+:\s+(.+)", cpuinfo)
            if model_match:
                model = model_match.group(1)
                print(f"🐧 Detected Raspberry Pi model: {model}")
                if "Zero" in model:
                    return "Pi Zero"
                elif "5" in model:
                    return "Pi 5"
    except Exception as e:
        print("⚠️ Failed to detect Pi model:", e)
    return "Unknown"

def load_openai_key():
    try:
        with open("part1.txt", "r") as f1, open("part2.txt", "r") as f2:
            return (f1.read().strip() + f2.read().strip())
    except FileNotFoundError:
        print("❌ API key parts not found.")
        sys.exit(1)

def load_whisper_model(size="base"):
    print(f"🔍 Loading Whisper model: {size}")
    return whisper.load_model(size)

def detect_microphone():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return any(d['max_input_channels'] > 0 for d in devices)
    except Exception as e:
        print("⚠️ Microphone detection failed:", e)
    return False

def detect_speaker():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return any(d['max_output_channels'] > 0 and 'dummy' not in d['name'].lower() for d in devices)
    except Exception as e:
        print("⚠️ Speaker detection failed:", e)
    return False

# ========== AUDIO RECORDING ==========

def record_audio_interactive(output_path="input.wav", duration=None):
    print("🎤 Using fallback recorder (arecord)...")
    stop_event.clear()

    def enter_listener():
        time.sleep(0.3)
        print("🛑 Press ENTER or press the BUTTON again to stop recording.")
        input()
        stop_event.set()

    threading.Thread(target=enter_listener, daemon=True).start()

    print("📼 Recording...")
    cmd = ["arecord", "-D", "plughw:2,0", "-f", "cd", output_path]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        proc.terminate()
        proc.wait()
        print(f"💾 Audio saved to {output_path}")
        time.sleep(0.5)

    return output_path

# ========== CORE LOGIC FUNCTIONS ==========

def transcribe_audio_local(model, audio_path):
    print(f"🎙️ Transcribing locally: {audio_path}")
    result = model.transcribe(audio_path, language="en")
    print("🗣️ You said:", result["text"])
    return result["text"]

def transcribe_audio_openai(client, audio_path):
    print(f"🎙️ Transcribing via OpenAI API: {audio_path}")
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"
        )
    print("🗣️ You said:", transcript.text)
    return transcript.text

def query_llm(client, prompt, model_name, use_local=False):
    if use_local:
        print("🧠 Using local LLM...")
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=LOCAL_LLM_PATH, n_ctx=1024)
            result = llm(SYSTEM_PROMPT + prompt, max_tokens=200)
            reply = result["choices"][0]["text"].strip()
            print("💬 Local LLM Response:", reply)
            return reply
        except Exception as e:
            print("❌ Local LLM failed:", e)
            return "I'm offline and unable to respond."
    else:
        print("🤖 Querying ChatGPT...")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": SYSTEM_PROMPT + prompt}]
        )
        reply = response.choices[0].message.content.strip()
        print("💬 GPT Response:", reply)
        return reply

def synthesize_speech(text, output_path=None, use_local=False):
    if not output_path:
        output_path = f"response_{uuid.uuid4().hex}.mp3"

    if use_local:
        print("🎧 Generating speech with espeak (offline)...")
        output_wav = output_path.replace(".mp3", ".wav")
        try:
            subprocess.run(["espeak", text, "-w", output_wav])
            return output_wav
        except Exception as e:
            print("❌ espeak failed:", e)
            return None
    else:
        print("🎧 Generating TTS via gTTS (online)...")
        tts = gTTS(text)
        tts.save(output_path)
        return output_path

def play_audio(path):
    print(f"🔊 Playing audio: {path}")
    try:
        if IS_MAC:
            subprocess.run(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif path.endswith(".wav"):
            subprocess.run(["aplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["mpg123", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("⚠️ Playback error:", e)

# ========== INTERACTION FUNCTIONS ==========

def start_interaction():
    set_state("listening")
    record_audio_interactive(output_path=AUDIO_INPUT_PATH)

    set_state("processing")
    if USE_LOCAL_STT:
        user_text = transcribe_audio_local(whisper_model, AUDIO_INPUT_PATH)
    else:
        user_text = transcribe_audio_openai(client, AUDIO_INPUT_PATH)

    reply_text = query_llm(client, user_text, OPENAI_MODEL, use_local=USE_LOCAL_LLM)
    audio_path = synthesize_speech(reply_text, use_local=USE_LOCAL_TTS)

    set_state("speaking")
    if has_speaker and audio_path:
        play_audio(audio_path)
    else:
        print("🔇 No speaker detected or audio not generated.")

    print("📥 Press the button or ENTER to start...")


def safe_start_interaction():
    if not interaction_lock.acquire(blocking=False):
        print("⏳ Already running, ignoring extra trigger.")
        return
    try:
        start_interaction()
        time.sleep(0.5)
    finally:
        interaction_lock.release()

# ========== BUTTON LISTENER LOOP ==========

def button_loop():
    while True:
        button.wait_for_press()
        if state == "ready":
            safe_start_interaction()
        elif state == "listening":
            stop_event.set()
        time.sleep(0.3)

# ========== ENTER KEY LISTENER ==========

def wait_for_enter_key():
    while True:
        input("🖱️ Press ENTER to start interaction...\n")
        safe_start_interaction()

# ========== INIT & RUN ==========

if __name__ == "__main__":
    pi_model = detect_pi_model()
    online = is_online()
    print(f"🌐 Online: {online}")

    if pi_model == "Pi 5" and not online:
        USE_LOCAL_STT = True
        USE_LOCAL_LLM = True
        USE_LOCAL_TTS = True

    print(f"🧩 Using local STT: {USE_LOCAL_STT}")
    print(f"🧩 Using local LLM: {USE_LOCAL_LLM}")
    print(f"🧩 Using local TTS: {USE_LOCAL_TTS}")

    os.environ["OPENAI_API_KEY"] = load_openai_key()
    client = OpenAI()
    whisper_model = load_whisper_model(MODEL_SIZE) if USE_LOCAL_STT else None

    has_mic = detect_microphone()
    has_speaker = detect_speaker()

    set_state("ready")

    threading.Thread(target=button_loop, daemon=True).start()
    threading.Thread(target=wait_for_enter_key, daemon=True).start()

    print("📥 Press the button or ENTER to start...")

    try:
        pause()
    except KeyboardInterrupt:
        print("\n👋 Exiting with Ctrl+C...")
    finally:
        GPIO.cleanup()
