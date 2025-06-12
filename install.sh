#!/bin/bash
pip install openai torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install git+https://github.com/openai/whisper.git
pip install gtts sounddevice soundfile