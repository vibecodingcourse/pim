import sounddevice as sd
import numpy as np

print("🎤 Recording 3 seconds...")
fs = 44100
duration = 3
recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
sd.wait()

print("🔊 Playing back...")
sd.play(recording, samplerate=fs)
sd.wait()