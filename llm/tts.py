"""Text to speech for the patient (Gemini TTS), returned as a WAV file.

The voice is picked by the patient's sex and the speaking style is built from the case on the
server, so age and personality never reach the browser. Voices chosen by ear on 2026-10-25 from a
sampler of Gemini voices (flash-lite and flash sounded the same; lite is faster).
"""

import io
import wave

from llm.gemini import MODELS, with_rotation

VOICES = {"femenino": "Sulafat", "masculino": "Schedar"}
SAMPLE_RATE = 24000  # Gemini TTS returns 16-bit mono PCM at 24 kHz


def style(case: dict) -> str:
    """Speaking style for the case, sent apart from the text (inside the text it would be read aloud)."""
    p = case["paciente"]
    quien = "mujer uruguaya" if p["sexo"] == "femenino" else "hombre uruguayo"
    tipo = case.get("personalidad", {}).get("tipo", "")
    return f"{quien} de {p['edad']} años, de Montevideo, acento rioplatense, {tipo}, habla natural, como un paciente en la consulta"


def to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def synthesize(text: str, case: dict) -> bytes:
    """WAV audio of `text` spoken as the case's patient. Rotates keys and models on quota errors."""
    from google import genai
    from google.genai import types

    voice = VOICES.get(case["paciente"]["sexo"], VOICES["masculino"])
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
    )
    contents = [types.Content(role="user", parts=[
        types.Part(text=text, speech_metadata=types.SpeechMetadata(style=style(case)))])]

    def call(key: str, model: str) -> bytes:
        client = genai.Client(api_key=key)  # keep the reference: an inline client is closed before the call
        res = client.models.generate_content(model=model, contents=contents, config=config)
        pcm = b"".join(p.inline_data.data for p in res.candidates[0].content.parts if p.inline_data)
        if not pcm:
            raise RuntimeError(f"{model} returned no audio")
        return pcm

    return to_wav(with_rotation(call, "tts", retries=0))
