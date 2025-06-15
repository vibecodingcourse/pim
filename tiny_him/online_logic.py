from openai import OpenAI
import uuid

def transcribe_audio(client, audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"
        )
    return transcript.text

def query_chatgpt(client, user_input, model, system_prompt):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": system_prompt + user_input}]
    )
    return response.choices[0].message.content.strip()

def synthesize_speech_openai(client, text, output_path=None):
    if not output_path:
        output_path = f"response_{uuid.uuid4().hex}.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text
    )
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path