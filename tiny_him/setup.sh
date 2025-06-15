#!/bin/bash

echo "🔧 Installing system packages..."
sudo apt update
sudo apt install -y mpg123 espeak alsa-utils python3-pip

echo "🐍 Installing Python dependencies..."
pip3 install -r requirements.txt

echo "✅ Done. You can now run: python3 main.py"