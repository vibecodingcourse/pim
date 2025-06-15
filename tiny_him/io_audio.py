import subprocess
import uuid
import time
import platform
import os

IS_MAC = platform.system() == "Darwin"

def record_audio_interactive(output_path="input.wav", stop_event=None):
    print("🎤 Recording with arecord...")
    cmd = ["arecord", "-D", "plughw:2,0", "-f", "cd", output_path]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        proc.terminate()
        proc.wait()
        print(f"💾 Audio saved to {output_path}")

def play_audio(path):
    print(f"🔊 Playing: {path}")
    if IS_MAC:
        subprocess.run(["afplay", path])
    elif path.endswith(".wav"):
        subprocess.run(["aplay", path])
    else:
        subprocess.run(["mpg123", path])