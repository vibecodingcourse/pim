import whisper
from gtts import gTTS
import uuid
import subprocess
import sounddevice as sd
import soundfile as sf
import threading
import queue
import sys
import platform
import os
import re
import socket
import time
from openai import OpenAI
from gpiozero import Button, LED
from signal import pause

# ========== CONFIG ==========
AUDIO_INPUT_PATH = "input.wav"
MODEL_SIZE = "base"
OPENAI_MODEL = "gpt-4.1"
LOCAL_LLM_PATH = "phi-2.Q4_K_M.gguf"
IS_MAC = platform.system() == "Darwin"

# Flags (auto-set)
USE_LOCAL_STT = False
USE_LOCAL_LLM = False
USE_LOCAL_TTS = False

# ========== GPIO ==========
button = Button(17, pull_up=True, bounce_time=0.1)
led = LED(18)
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
            state = "idle"
        else:
            led.off(); time.sleep(0.1)

def set_state(new_state):
    global state
    state = new_state
    print(f"🔁 State: {state}")

threading.Thread(target=led_loop, daemon=True).start()

# ========== UTILITIES ==========
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
        devices = sd.query_devices()
        return any(d['max_input_channels'] > 0 for d in devices)
    except Exception as e:
        print("⚠️ Microphone detection failed:", e)
    return False

def detect_speaker():
    try:
        devices = sd.query_devices()
        return any(d['max_output_channels'] > 0 and 'dummy' not in d['name'].lower() for d in devices)
    except Exception as e:
        print("⚠️ Speaker detection failed:", e)
    return False

# ========== AUDIO RECORDING ==========
stop_signal = threading.Event()

def wait_for_enter_or_button():
    print("🎙️ Press ENTER or button to stop recording...")
    while not stop_signal.is_set():
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()
            stop_signal.set()

def record_audio_interactive(output_path="input.wav", samplerate=None, channels=1):
    print("🎙️ Press ENTER or button to start recording...")
    while not button.is_pressed:
        if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
            sys.stdin.readline()
            break
        time.sleep(0.05)

    set_state("listening")
    print("⏺️ Recording...")

    stop_signal.clear()
    q = queue.Queue()
    recording = True

    mic_index = None
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0 and 'monitor' not in dev['name'].lower() and 'dummy' not in dev['name'].lower():
                mic_index = idx
                samplerate = int(dev['default_samplerate']) if samplerate is None else samplerate
                break
    except Exception as e:
        print("⚠️ Could not list input devices:", e)

    def callback(indata, frames, time, status):
        if status:
            print("⚠️", status, file=sys.stderr)
        q.put(indata.copy())

    def stop_thread():
        while not stop_signal.is_set():
            if button.is_pressed:
                stop_signal.set()
            time.sleep(0.05)

    threading.Thread(target=wait_for_enter_or_button).start()
    threading.Thread(target=stop_thread).start()

    with sf.SoundFile(output_path, mode='w', samplerate=samplerate, channels=channels) as file:
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback, device=mic_index):
            while not stop_signal.is_set():
                file.write(q.get())

    print(f"💾 Audio saved to {output_path}")
    return output_path

# ========== CORE FUNCTIONS ==========
def transcribe_audio_local(model, audio_path):
    print(f"🎙️ Transcribing locally: {audio_path}")
    result = model.transcribe(audio_path)
    print("🗣️ You said:", result["text"])
    return result["text"]

def transcribe_audio_openai(client, audio_path):
    print(f"🎙️ Transcribing via OpenAI API: {audio_path}")
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    print("🗣️ You said:", transcript.text)
    return transcript.text

def query_llm(client, prompt, model_name, use_local=False):
    if use_local:
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=LOCAL_LLM_PATH, n_ctx=1024)
            result = llm("You are a helpful assistant. " + prompt, max_tokens=200)
            return result["choices"][0]["text"].strip()
        except Exception as e:
            return "I'm offline and unable to respond."
    else:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

def synthesize_speech(text, output_path=None, use_local=False):
    if not output_path:
        output_path = f"response_{uuid.uuid4().hex}.mp3"
    if use_local:
        output_wav = output_path.replace(".mp3", ".wav")
        subprocess.run(["espeak", text, "-w", output_wav])
        return output_wav
    else:
        gTTS(text).save(output_path)
        return output_path

def play_audio(path):
    if IS_MAC:
        subprocess.run(["afplay", path])
    elif path.endswith(".wav"):
        subprocess.run(["aplay", path])
    else:
        subprocess.run(["mpg123", path])

# ========== MAIN ==========
if __name__ == "__main__":
    import select

    pi_model = detect_pi_model()
    online = is_online()
    if pi_model == "Pi 5" and not online:
        USE_LOCAL_STT = USE_LOCAL_LLM = USE_LOCAL_TTS = True

    has_mic = detect_microphone()
    has_speaker = detect_speaker()

    os.environ["OPENAI_API_KEY"] = load_openai_key()
    client = OpenAI()
    whisper_model = load_whisper_model(MODEL_SIZE) if USE_LOCAL_STT else None

    set_state("ready")
    print("🌀 Ready! Press the button or ENTER to ask.")

    while True:
        try:
            audio_path = record_audio_interactive(output_path=AUDIO_INPUT_PATH)

            set_state("processing")
            if USE_LOCAL_STT:
                user_text = transcribe_audio_local(whisper_model, audio_path)
            else:
                user_text = transcribe_audio_openai(client, audio_path)

            reply = query_llm(client, user_text, OPENAI_MODEL, use_local=USE_LOCAL_LLM)

            set_state("speaking")
            output_audio = synthesize_speech(reply, use_local=USE_LOCAL_TTS)

            if has_speaker:
                play_audio(output_audio)
            else:
                print(reply)

            set_state("idle")

        except KeyboardInterrupt:
            running = False
            print("\n👋 Exiting.")
            break