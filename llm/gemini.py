"""Modelos de Gemini por tarea y rotación de API keys.

Las keys se leen de .env como GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ... (o una sola
GOOGLE_API_KEY). Cuando una key devuelve 429 (sin cuota), se pasa a la siguiente.

Los modelos disponibles cambian seguido: `python llm/probe_models.py` prueba cuáles
andan con cada key y en qué tiempo, para actualizar MODELS.
"""

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, TypeVar

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# Trazas de LangSmith: se activan con LANGSMITH_TRACING=true y LANGSMITH_API_KEY en .env
os.environ.setdefault("LANGSMITH_PROJECT", "chiron")

# Probado el 2026-10-24 en plan gratuito. Los "pro" (3.1-pro, pro-latest, 4-argon) dan 429 con cuota 0.
# gemini-3.7/3.8-flash y flash-latest andan pero tardaron 30-75 s por respuesta: no sirven para conversar.
# Con thinking_level="low", gemini-3-flash-preview responde al paciente en ~1 s (3.5-flash: ~1,5-2 s).
MODELS = {
    # respuestas del paciente: rápido, buena calidad
    # los flash tienen 20 requests/día por key en plan gratuito: el lite queda de último respaldo
    "patient": ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
    # router y decisiones cortas: lo más rápido posible
    "router": ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"],
    # juez del feedback: calidad sobre velocidad
    "judge": ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"],
    # voz en tiempo real (Live API)
    "live": ["gemini-3.8-live", "gemini-3.1-flash-live-preview"],
    "embedding": ["gemini-embedding-001"],
}

T = TypeVar("T")


def api_keys() -> list[str]:
    numbered = sorted(k for k in os.environ if k.startswith("GOOGLE_API_KEY_"))
    keys = [os.environ[k] for k in numbered if os.environ[k]]
    if not keys and os.environ.get("GOOGLE_API_KEY"):
        keys = [os.environ["GOOGLE_API_KEY"]]
    if not keys:
        raise RuntimeError("No hay GOOGLE_API_KEY_N en .env")
    return keys


def is_quota_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code == 429 or "RESOURCE_EXHAUSTED" in str(exc)


@lru_cache(maxsize=None)
def _client(model: str, key: str, kwargs: tuple):
    """Instancia de ChatGoogleGenerativeAI compartida (crear cada una tarda ~1 s)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, google_api_key=key, max_retries=0, **dict(kwargs))


def chat_model(task: str, schema: type | None = None, **kwargs):
    """Modelo de chat de LangChain para la tarea, con fallback por key y por modelo.

    Devuelve un Runnable: el primero es MODELS[task][0] con la primera key; ante
    cualquier error pasa a la siguiente key y después al siguiente modelo.
    Con `schema` (clase Pydantic) devuelve salida estructurada.
    """
    runnables = []
    for model in MODELS[task]:
        for key in api_keys():
            llm = _client(model, key, tuple(sorted(kwargs.items())))
            runnables.append(llm.with_structured_output(schema) if schema else llm)
    # si todas las keys y modelos fallan (p. ej. todas sin cuota por minuto), reintenta con espera creciente
    return runnables[0].with_fallbacks(runnables[1:]).with_retry(
        stop_after_attempt=4, wait_exponential_jitter=True, exponential_jitter_params={"initial": 5, "max": 40}
    )


def with_rotation(call: Callable[[str, str], T], task: str, retries: int = 3, wait: float = 30) -> T:
    """Ejecuta call(api_key, model) probando cada modelo de la tarea con cada key.

    Ante 429 pasa a la siguiente key; si todas se quedaron sin cuota para ese
    modelo, pasa al siguiente modelo. Si no queda ninguno, espera `wait` segundos
    (los límites del plan gratuito son por minuto) y reintenta hasta `retries`
    veces. Otros errores se propagan.
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(wait)
        for model in MODELS[task]:
            for key in api_keys():
                try:
                    return call(key, model)
                except Exception as exc:  # LangChain envuelve los errores de google-genai
                    if not is_quota_error(exc):
                        raise
                    last = exc
    raise RuntimeError(f"Todas las keys sin cuota para '{task}'") from last
