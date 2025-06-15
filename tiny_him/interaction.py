from io_audio import record_audio_interactive, play_audio
from gpio_handler import set_state
import threading

def run_interaction(client, config, stop_event, whisper_model=None, online=True):
    set_state("listening")
    record_audio_interactive(config.AUDIO_INPUT_PATH, stop_event)

    set_state("processing")
    if online:
        from online_logic import transcribe_audio, query_chatgpt, synthesize_speech_openai
        user_text = transcribe_audio(client, config.AUDIO_INPUT_PATH)
        reply_text = query_chatgpt(client, user_text, config.OPENAI_MODEL, config.SYSTEM_PROMPT)
        audio_path = synthesize_speech_openai(client, reply_text)
    else:
        from offline_logic import transcribe_audio_local, query_local_llm, synthesize_speech_local
        user_text = transcribe_audio_local(whisper_model, config.AUDIO_INPUT_PATH)
        reply_text = query_local_llm(user_text, config.LOCAL_LLM_PATH, config.SYSTEM_PROMPT)
        audio_path = synthesize_speech_local(reply_text)

    set_state("speaking")
    play_audio(audio_path)
    set_state("ready")