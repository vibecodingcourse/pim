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
from openai import OpenAI

# ========== CONFIG ==========

AUDIO_INPUT_PATH = "input.wav"
MODEL_SIZE = "base"
OPENAI_MODEL = "gpt-4.1"
LOCAL_LLM_PATH = "phi-2.Q4_K_M.gguf"
IS_MAC = platform.system() == "Darwin"

# Fallback flags (auto-set below)
USE_LOCAL_STT = False
USE_LOCAL_LLM = False
USE_LOCAL_TTS = False

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

# ========== SETUP FUNCTIONS ==========

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

def record_audio_interactive(output_path="input.wav", samplerate=None, channels=1):
    print("🎙️ Press ENTER to start recording...")
    input()
    print("⏺️ Recording... Press ENTER again to stop.")

    q = queue.Queue()
    recording = True

    # Select the first real input device
    mic_index = None
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            name = dev['name'].lower()
            if dev['max_input_channels'] > 0 and 'monitor' not in name and 'dummy' not in name:
                mic_index = idx
                print(f"🎤 Selected input device: {dev['name']} (device #{idx})")
                if samplerate is None:
                    samplerate = int(dev['default_samplerate'])
                    print(f"🎚️ Using supported sample rate: {samplerate}")
                break
    except Exception as e:
        print("⚠️ Could not list input devices:", e)

    if mic_index is None:
        print("⚠️ No suitable mic found. Using default.")
        mic_index = None

    def callback(indata, frames, time, status):
        if status:
            print("⚠️", status, file=sys.stderr)
        q.put(indata.copy())

    with sf.SoundFile(output_path, mode='w', samplerate=samplerate, channels=channels) as file:
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback, device=mic_index):
            def stopper():
                nonlocal recording
                input()
                recording = False

            threading.Thread(target=stopper).start()
            while recording:
                file.write(q.get())

    print(f"💾 Audio saved to {output_path}")
    return output_path

# ========== CORE LOGIC FUNCTIONS ==========

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
        print("🧠 Using local LLM...")
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=LOCAL_LLM_PATH, n_ctx=1024)
            system_prompt = "You are a helpful assistant. Answer concisely:\n"
            result = llm(system_prompt + prompt, max_tokens=200)
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
            messages=[{"role": "user", "content": prompt}]
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
    except FileNotFoundError:
        print("❌ 'mpg123' or 'aplay' not installed. Run: sudo apt install mpg123 aplay")
    except Exception as e:
        print("⚠️ Playback error:", e)

# ========== MAIN ENTRY POINT ==========

def main():
    global USE_LOCAL_STT, USE_LOCAL_LLM, USE_LOCAL_TTS

    # Detect system status
    pi_model = detect_pi_model()
    online = is_online()
    print(f"🌐 Online: {online}")

    # Set fallback flags
    if pi_model == "Pi 5" and not online:
        USE_LOCAL_STT = True
        USE_LOCAL_LLM = True
        USE_LOCAL_TTS = True
    else:
        USE_LOCAL_STT = False
        USE_LOCAL_LLM = False
        USE_LOCAL_TTS = False

    print(f"🧩 Using local STT: {USE_LOCAL_STT}")
    print(f"🧩 Using local LLM: {USE_LOCAL_LLM}")
    print(f"🧩 Using local TTS: {USE_LOCAL_TTS}")

    # Detect devices
    has_mic = detect_microphone()
    has_speaker = detect_speaker()

    # Load APIs and models
    os.environ["OPENAI_API_KEY"] = load_openai_key()
    client = OpenAI()
    whisper_model = load_whisper_model(MODEL_SIZE) if USE_LOCAL_STT else None

    print("🌀 Ready. Say or type 'exit' to quit.\n")

    while True:
        try:
            # Get input
            if has_mic:
                record_audio_interactive(output_path=AUDIO_INPUT_PATH)
                if USE_LOCAL_STT:
                    user_text = transcribe_audio_local(whisper_model, AUDIO_INPUT_PATH)
                else:
                    user_text = transcribe_audio_openai(client, AUDIO_INPUT_PATH)
            else:
                user_text = input("⌨️ Type your question: ")

            user_text = user_text.strip().lower()
            if user_text in ["exit", "quit", "bye"]:
                print("👋 Goodbye!")
                break

            # Get reply
            reply_text = query_llm(client, user_text, OPENAI_MODEL, use_local=USE_LOCAL_LLM)

            # Generate audio
            audio_path = synthesize_speech(reply_text, use_local=USE_LOCAL_TTS)

            # Output
            print("🖨️ Output:", reply_text)
            if has_speaker and audio_path:
                play_audio(audio_path)
            else:
                print("🔇 No speaker detected or audio not generated.")

        except KeyboardInterrupt:
            print("\n👋 Exiting by Ctrl+C")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            
if __name__ == "__main__":
    main()