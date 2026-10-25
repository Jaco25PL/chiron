"""Chiron HTTP API + static frontend.

    .venv\\Scripts\\python -m uvicorn api.main:app --reload --port 8000

With CHIRON_FAKE=1 it uses api/fake_session.py (no LLM). Otherwise it uses agents.session
and, if that can't be imported, falls back to the fake with a console warning.
"""

import base64
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from api.security import Unauthorized, verify  # noqa: E402

log = logging.getLogger("chiron.api")

BACKEND = "real"
if os.environ.get("CHIRON_FAKE") == "1":
    from api import fake_session as session
    BACKEND = "fake"
else:
    try:
        from agents import session  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"[chiron] WARNING: could not import agents.session ({e!r}); using api/fake_session.py",
              file=sys.stderr)
        from api import fake_session as session
        BACKEND = "fake"

app = FastAPI(title="Chiron")


@app.on_event("startup")
def _warm_up():
    """Creates the Gemini clients in the background so the first message doesn't have to wait."""
    if BACKEND == "real":
        import threading

        from agents.graph import models

        threading.Thread(target=models, daemon=True).start()


class AgentError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


@app.exception_handler(AgentError)
async def _agent_error(_: Request, exc: AgentError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    msgs = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=422, content={"error": f"Pedido inválido: {msgs}"})


def current_user(request: Request) -> dict:
    """Identity forwarded (and signed) by the Next.js server; see api/security.py."""
    try:
        return verify(request.headers)
    except Unauthorized as e:
        raise AgentError(401, f"No autorizado: {e}")


def _call(fn, *args, **kwargs):
    """Calls the backend and turns any exception into a JSON {error}."""
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise AgentError(404, f"No encontrado: {e}")
    except PermissionError:
        raise AgentError(403, "Esta consulta es de otro usuario")
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        raise AgentError(500, f"{type(e).__name__}: {e}")


class NewSession(BaseModel):
    case_id: str
    mode: str = "chat"
    nivel: Literal["normal", "principiante"] = "normal"  # agents/grilla.py LEVELS


class Message(BaseModel):
    text: str


class ReviewLabel(BaseModel):
    etiquetas: dict[str, bool | None]
    nota: str = ""


@app.get("/api/health")
def health():
    return {"ok": True, "backend": BACKEND}


@app.get("/api/cases")
def cases(materia: str = "mpna", user: dict = Depends(current_user)):
    return _call(session.list_cases, materia)


@app.post("/api/sessions")
def create_session(body: NewSession, user: dict = Depends(current_user)):
    """case_id: a public id from /api/cases, or "aleatorio". Returns who the patient is (name and
    sex only), so the UI learns it here even for a random case. In "principiante" it also brings the
    checklist, all unticked."""
    sid = _call(session.new_session, body.case_id, user, body.mode, body.nivel)
    s = _call(session.get_session, sid, user)
    return {"session_id": sid, "case": s["case"], **({"checklist": s["checklist"]} if "checklist" in s else {})}


@app.post("/api/sessions/{session_id}/messages")
def send_message(session_id: str, body: Message, voz: bool = False, user: dict = Depends(current_user)):
    """With voz=1 (the face-to-face call) the reply is streamed as NDJSON together with the patient's voice."""
    if not body.text.strip():
        raise AgentError(400, "Mensaje vacío")
    result = _call(session.send, session_id, body.text, user)
    if not voz:
        return result
    return StreamingResponse(_with_voice(session_id, user, result), media_type="application/x-ndjson")


def _with_voice(session_id: str, user: dict, result: dict):
    """One line per event: the reply first (shown at once), then the patient's voice as base64 PCM
    (24 kHz, 16-bit mono) while Gemini generates it, so it starts playing with the first chunk instead
    of after a second request and the whole file. Only the reply just generated is ever spoken."""
    yield json.dumps({"tipo": "respuesta", **result}) + "\n"
    if result["replies"] and result["replies"][-1]["role"] == "paciente":
        try:
            for pcm in session.speak(session_id, user):
                yield json.dumps({"tipo": "audio", "pcm": base64.b64encode(pcm).decode()}) + "\n"
        except Exception as e:  # noqa: BLE001  the text already arrived: the call goes on with subtitles
            traceback.print_exc()
            yield json.dumps({"tipo": "error", "error": f"{type(e).__name__}: {e}"}) + "\n"
    yield json.dumps({"tipo": "fin"}) + "\n"


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, user: dict = Depends(current_user)):
    return _call(session.get_session, session_id, user)


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str, user: dict = Depends(current_user)):
    return _call(session.finish, session_id, user)


@app.get("/api/historial")
def historial(user: dict = Depends(current_user)):
    """The caller's finished consultations with their score, newest first (public view of the patient only)."""
    return _call(session.historial, user)


def reviewer(user: dict = Depends(current_user)) -> str:
    """Only the medical reviewers in CHIRON_REVIEWERS (any user in local dev, without the secret):
    the items show the hidden diagnoses."""
    from store import review

    email = (user["email"] or "").lower()
    if os.environ.get("CHIRON_BACKEND_SECRET") and email not in review.reviewers():
        raise AgentError(403, "Esta página es solo para quienes revisan el corrector.")
    return email


@app.get("/api/revision")
def review_items(email: str = Depends(reviewer)):
    """The judge's answers to label (without its verdict), with this reviewer's labels so far."""
    from store import review

    return {"criterios": review.CRITERIA, "items": _call(review.items_for, email)}


@app.post("/api/revision/{item_id}")
def review_label(item_id: str, body: ReviewLabel, email: str = Depends(reviewer)):
    from store import review

    if not set(body.etiquetas) <= set(review.CRITERIA):
        raise AgentError(400, f"Criterio desconocido: {sorted(set(body.etiquetas) - set(review.CRITERIA))}")
    _call(review.save, item_id, email, body.etiquetas, body.nota[:2000])
    return {"ok": True}


@app.get("/api/rag/search")
def rag_search(q: str, materia: str = "mpna", k: int = Query(5, ge=1, le=30), tipo: str = "",
               user: dict = Depends(current_user)):
    def _search():
        from store import db
        if db.enabled():  # deployed: pgvector in Neon
            from rag.search import search
        else:  # local without a database: Chroma index
            from rag.query import search
        return search(materia, q, k=k, tipo=tipo or None)
    results = _call(_search)
    return [{**r, "score": float(r["score"])} for r in results]


class Preferencias(BaseModel):
    acento: str


@app.get("/api/preferencias")
def get_preferencias(user: dict = Depends(current_user)):
    from store import db  # imported here, like the routes above

    return {"acento": _call(db.get_acento, user["email"])}


@app.post("/api/preferencias")
def set_preferencias(body: Preferencias, user: dict = Depends(current_user)):
    from store import db

    if body.acento not in db.ACENTOS:
        raise AgentError(400, f"Color desconocido: {body.acento}")
    _call(db.set_acento, user["email"], user.get("name"), body.acento)
    return {"acento": body.acento}


# Legacy debug UI (chat + RAG explorer), local development only: it can't sign requests.
if not os.environ.get("CHIRON_BACKEND_SECRET") and (ROOT / "frontend").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
