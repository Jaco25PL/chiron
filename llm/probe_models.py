"""Prueba qué modelos de Gemini andan con cada key y cuánto tardan.

Uso:
    python llm/probe_models.py           # modelos de MODELS + candidatos nuevos
    python llm/probe_models.py --all     # todo lo que lista la API (más lento)
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor

from google import genai

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from gemini import MODELS, api_keys  # noqa: E402


def probe(key: str, model: str) -> str:
    client = genai.Client(api_key=key)
    start = time.time()
    try:
        if "embedding" in model:
            client.models.embed_content(model=model, contents="dolor torácico")
        else:
            client.models.generate_content(model=model, contents="Respondé solo: OK")
        return f"OK {time.time() - start:5.1f}s"
    except Exception as exc:  # noqa: BLE001 - queremos ver cualquier falla
        code = getattr(exc, "code", "?")
        return f"FAIL {code}" + (" sin cuota" if "limit: 0" in str(exc) else "")


def main():
    keys = api_keys()
    client = genai.Client(api_key=keys[0])
    listed = {
        m.name.removeprefix("models/")
        for m in client.models.list()
        if {"generateContent", "embedContent"} & set(m.supported_actions or [])
    }
    configured = {m for task, ms in MODELS.items() if task != "live" for m in ms}
    if "--all" in sys.argv:
        models = sorted(listed)
    else:
        new = {m for m in listed if m.startswith("gemini-") and "flash" in m and not any(
            x in m for x in ("image", "tts", "audio", "transcribe", "live"))}
        models = sorted(configured | new)

    missing = configured - listed
    if missing:
        print("Configurados pero ya no listados:", ", ".join(sorted(missing)))

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda a: probe(*a), [(k, m) for m in models for k in keys]))
    for i, model in enumerate(models):
        row = results[i * len(keys) : (i + 1) * len(keys)]
        mark = "*" if model in configured else " "
        print(f"{mark} {model:32s} | " + " | ".join(r.ljust(18) for r in row))
    print("\n* = en MODELS")


if __name__ == "__main__":
    main()
