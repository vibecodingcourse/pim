from llama_cpp import Llama
import whisper
import subprocess

def transcribe_audio_local(model, audio_path):
    return model.transcribe(audio_path, language="en")["text"]

def query_local_llm(prompt, model_path, system_prompt):
    llm = Llama(model_path=model_path, n_ctx=1024)
    result = llm(system_prompt + prompt, max_tokens=200)
    return result["choices"][0]["text"].strip()

def synthesize_speech_local(text, output_path="response.wav"):
    subprocess.run(["espeak", text, "-w", output_path])
    return output_path