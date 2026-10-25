"""Gemini models per task, and API key rotation.

Keys are read from .env as GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ... (or a single
GOOGLE_API_KEY). When a key returns 429 (out of quota), the next one is used.

Available models change often: `python llm/probe_models.py` checks which ones work
with each key and how fast, so MODELS can be kept up to date.
"""

import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, TypeVar

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# LangSmith tracing: enabled with LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env
os.environ.setdefault("LANGSMITH_PROJECT", "chiron")

# Tested on 2026-10-24 on the free tier. The "pro" models (3.1-pro, pro-latest, 4-argon) return 429 with zero quota.
# gemini-3.7/3.8-flash and flash-latest work but took 30-75 s per reply: too slow for conversation.
# With thinking_level="low", gemini-3-flash-preview answers as the patient in ~1 s (3.5-flash: ~1.5-2 s).
MODELS = {
    # patient replies: fast, good quality
    # flash models get 20 requests/day per key on the free tier: lite is the last fallback
    "patient": ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
    # router and short decisions: as fast as possible
    "router": ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"],
    # feedback judge: quality over speed
    "judge": ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"],
    # real-time voice (Live API)
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
        raise RuntimeError("No GOOGLE_API_KEY_N found in .env")
    return keys


def is_quota_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code == 429 or "RESOURCE_EXHAUSTED" in str(exc)


@lru_cache(maxsize=None)
def _client(model: str, key: str, kwargs: tuple):
    """Shared ChatGoogleGenerativeAI instance (creating each one takes ~1 s)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, google_api_key=key, max_retries=0, **dict(kwargs))


class QuotaBlocked(Exception):
    """The (model, key) pair ran out of quota recently: skip it without calling the API."""


# (model, key) -> timestamp until which it is not used. Avoids wasting ~0.3 s per call
# retrying combinations that already answered "out of quota for today".
_blocked: dict[tuple[str, str], float] = {}


def _block_seconds(exc: Exception) -> float:
    text = str(exc)
    if "PerDay" in text:
        m = re.search(r"retryDelay['\"]?:\s*['\"](\d+)s", text)
        return float(m.group(1)) if m else 3600.0
    return 20.0  # per-minute limit


def _guarded(make_runnable, model: str, key: str):
    """Wraps one (model, key) option: skips it while blocked and builds the client lazily,
    on its first real use (building every client up front cost ~20 s per cold start)."""
    from langchain_core.runnables import RunnableLambda

    built = []

    def call(value, config):
        if _blocked.get((model, key), 0) > time.time():
            raise QuotaBlocked(f"{model} out of quota")
        if not built:
            built.append(make_runnable())
        try:
            return built[0].invoke(value, config)
        except Exception as exc:
            if is_quota_error(exc):
                _blocked[(model, key)] = time.time() + _block_seconds(exc)
            raise

    return RunnableLambda(call, name=model)


def chat_model(task: str, schema: type | None = None, **kwargs):
    """LangChain chat model for the task, with fallback across keys and models.

    Returns a Runnable: the first one is MODELS[task][0] with the first key; on any
    error it moves to the next key and then to the next model. (model, key) pairs
    that are out of quota are skipped until it renews (see `_guarded`).
    With `schema` (a Pydantic class) it returns structured output.
    """
    frozen = tuple(sorted(kwargs.items()))

    def factory(model: str, key: str):
        def make():
            llm = _client(model, key, frozen)
            return llm.with_structured_output(schema) if schema else llm
        return make

    runnables = [_guarded(factory(model, key), model, key) for model in MODELS[task] for key in api_keys()]
    # if every key and model fails (e.g. all out of per-minute quota), retry with growing backoff
    return runnables[0].with_fallbacks(runnables[1:]).with_retry(
        stop_after_attempt=4, wait_exponential_jitter=True, exponential_jitter_params={"initial": 5, "max": 40}
    )


def with_rotation(call: Callable[[str, str], T], task: str, retries: int = 3, wait: float = 30) -> T:
    """Runs call(api_key, model), trying each of the task's models with each key.

    On 429 it moves to the next key; if all keys are out of quota for that model,
    it moves to the next model. If none is left, it waits `wait` seconds (free-tier
    limits are per minute) and retries up to `retries` times. Other errors propagate.
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(wait)
        for model in MODELS[task]:
            for key in api_keys():
                try:
                    return call(key, model)
                except Exception as exc:  # LangChain wraps google-genai errors
                    if not is_quota_error(exc):
                        raise
                    last = exc
    raise RuntimeError(f"All keys out of quota for '{task}'") from last
