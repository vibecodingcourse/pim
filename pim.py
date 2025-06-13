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
from openai import OpenAI

# ========== CONFIG ==========

AUDIO_INPUT_PATH = "input.wav"
MODEL_SIZE = "base"  # whisper: tiny, base, small, medium, large
IS_MAC = platform.system() == "Darwin"
HAS_MIC = False
HAS_SPEAKER = False


# ========== SETUP FUNCTIONS ==========

def load_openai_key(filepath="openai.txt"):
    with open(filepath, "r") as f:
        return f.read().strip()


def load_whisper_model(size="base"):
    print(f"🔍 Loading Whisper model: {size}")
    return whisper.load_model(size)


def detect_microphone():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device['max_input_channels'] > 0:
                return True
    except Exception as e:
        print("⚠️ Microphone detection failed:", e)
    return False


def detect_speaker():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device['max_output_channels'] > 0:
                return True
    except Exception as e:
        print("⚠️ Speaker detection failed:", e)
    return False


# ========== AUDIO RECORDING ==========

def record_audio_interactive(output_path="input.wav", samplerate=16000, channels=1):
    print("🎙️ Press ENTER to start recording...")
    input()
    print("⏺️ Recording... Press ENTER again to stop.")

    q = queue.Queue()
    recording = True

    def callback(indata, frames, time, status):
        if status:
            print("⚠️", status, file=sys.stderr)
        q.put(indata.copy())

    with sf.SoundFile(output_path, mode='w', samplerate=samplerate,
                      channels=channels) as file:
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
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

def transcribe_audio(model, audio_path):
    print(f"🎙️ Transcribing audio: {audio_path}")
    result = model.transcribe(audio_path)
    print("🗣️ You said:", result["text"])
    return result["text"]


def query_chatgpt(prompt, model="gpt-4"):
    print("🤖 Querying ChatGPT...")
    client = OpenAI()
    response = client.responses.create(
        model=model,
        input="Answer concisely the following question: " + prompt
    )
    reply = response.choices[0].message.content.strip()
    print("💬 GPT Response:", reply)
    return reply


def synthesize_speech(text, output_path=None):
    if not output_path:
        output_path = f"response_{uuid.uuid4().hex}.mp3"
    print("🎧 Generating TTS...")
    tts = gTTS(text)
    tts.save(output_path)
    return output_path


def play_audio(path):
    print(f"🔊 Playing audio: {path}")
    if IS_MAC:
        subprocess.run(["afplay", path])
    else:
        subprocess.run(["mpg123", path])


# ========== MAIN ENTRY POINT ==========

def main():
    global client, HAS_MIC, HAS_SPEAKER

    # Detect capabilities
    HAS_MIC = detect_microphone()
    HAS_SPEAKER = detect_speaker()

    # Load OpenAI and Whisper
    openai_key = load_openai_key()
    client = OpenAI()
    whisper_model = load_whisper_model(MODEL_SIZE)

    # Input: Mic or keyboard
    if HAS_MIC:
        record_audio_interactive(output_path=AUDIO_INPUT_PATH)
        user_text = transcribe_audio(whisper_model, AUDIO_INPUT_PATH)
    else:
        user_text = input("⌨️ Type your question: ")

    # GPT + TTS
    reply_text = query_chatgpt(user_text)
    audio_path = synthesize_speech(reply_text)

    # Output: Print always, play if speaker
    print("🖨️ Output:", reply_text)
    if HAS_SPEAKER:
        play_audio(audio_path)
    else:
        print("🔇 No speaker detected — skipping audio playback.")


if __name__ == "__main__":
    main()