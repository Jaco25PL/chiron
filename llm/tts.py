"""Text to speech for the patient and the study companion (Gemini TTS), streamed as PCM.

The voice is picked by the patient's sex and the speaking style is built from the case on the
server, so age and personality never reach the browser. Voices chosen by ear on 2026-10-25 from a
sampler of Gemini voices (flash-lite and flash sounded the same; lite is faster).
"""

import io
import wave
from collections.abc import Iterator

VOICES = {"femenino": "Sulafat", "masculino": "Schedar"}
# the study companion (agents/tutor.py): a young woman, distinct from every patient's voice
TUTOR_VOICE = "Despina"  # picked by ear on 2026-10-28 among 8 young female voices
TUTOR_STYLE = ("mujer joven uruguaya, unos 24 años, acento rioplatense de Montevideo, cálida y cercana, "
               "entusiasta pero tranquila, como una compañera de facultad que te da una mano")
SAMPLE_RATE = 24000  # Gemini TTS audio is 16-bit mono PCM at 24 kHz


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


def to_pcm(audio: bytes) -> bytes:
    """Raw PCM from a TTS part. Newer models return a whole WAV whose last chunk is a C2PA provenance
    signature: wrapped as-is it played as a burst of static at the end, so keep only the data chunk."""
    if audio[:4] != b"RIFF":
        return audio
    with wave.open(io.BytesIO(audio)) as w:
        return w.readframes(w.getnframes())


def _audio(chunks, usage: dict) -> Iterator[bytes]:
    for chunk in chunks:
        if chunk.usage_metadata:  # running totals; the last chunk has the final ones
            usage["in"] = chunk.usage_metadata.prompt_token_count or 0
            usage["out"] = (chunk.usage_metadata.total_token_count or 0) - usage["in"]
        content = chunk.candidates[0].content if chunk.candidates else None
        for part in content.parts if content and content.parts else []:
            if part.inline_data and part.inline_data.data:
                yield to_pcm(part.inline_data.data)


def stream(text: str, case: dict) -> Iterator[bytes]:
    """PCM chunks of `text` spoken as the case's patient (see `speak_as`)."""
    return speak_as(text, VOICES.get(case["paciente"]["sexo"], VOICES["masculino"]), style(case))


def stream_tutor(text: str) -> Iterator[bytes]:
    """PCM chunks of `text` in the study companion's voice."""
    return speak_as(text, TUTOR_VOICE, TUTOR_STYLE)


def speak_as(text: str, voice: str, speaking_style: str) -> Iterator[bytes]:
    """PCM chunks of `text` in this voice and style, as Gemini generates them (faster than they play:
    the first one arrives in about a second). Rotates keys and models on quota errors."""
    # imported here so the fake backend (CI E2E installs only fastapi + uvicorn) can import this module
    from google import genai
    from google.genai import types

    from llm.gemini import record_usage, with_rotation

    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
    )
    contents = [types.Content(role="user", parts=[
        types.Part(text=text, speech_metadata=types.SpeechMetadata(style=speaking_style))])]

    def call(key: str, model: str):
        client = genai.Client(api_key=key)  # keep the reference: an inline client is closed before the call
        usage = {"in": 0, "out": 0}
        audio = _audio(client.models.generate_content_stream(model=model, contents=contents, config=config), usage)
        first = next(audio, None)  # quota errors surface here, where with_rotation can still switch keys
        if first is None:
            raise RuntimeError(f"{model} returned no audio")
        return client, first, audio, usage, key, model

    _client, first, audio, usage, key, model = with_rotation(call, "tts", retries=0)
    try:
        yield first
        yield from audio
    finally:  # also when the student interrupts and the stream is closed early
        record_usage(key, model, usage["in"], usage["out"])
