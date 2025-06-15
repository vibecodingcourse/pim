import socket
import platform
import re

def is_mac():
    return platform.system() == "Darwin"

def detect_pi_model():
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            model_match = re.search(r"Model\s+:\s+(.+)", cpuinfo)
            if model_match:
                model = model_match.group(1)
                if "Zero" in model:
                    return "Pi Zero"
                elif "5" in model:
                    return "Pi 5"
    except Exception:
        pass
    return "Unknown"

def is_online(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

def detect_microphone():
    try:
        import sounddevice as sd
        return any(d['max_input_channels'] > 0 for d in sd.query_devices())
    except Exception:
        return False

def detect_speaker():
    try:
        import sounddevice as sd
        return any(d['max_output_channels'] > 0 and 'dummy' not in d['name'].lower() for d in sd.query_devices())
    except Exception:
        return False