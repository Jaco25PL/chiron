"""Chiron HTTP API + static frontend.

    .venv\\Scripts\\python -m uvicorn api.main:app --reload --port 8000

With CHIRON_FAKE=1 it uses api/fake_session.py (no LLM). Otherwise it uses agents.session
and, if that can't be imported, falls back to the fake with a console warning.
"""

import logging
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

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


def _call(fn, *args, **kwargs):
    """Calls the backend and turns any exception into a JSON {error}."""
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise AgentError(404, f"No encontrado: {e}")
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        raise AgentError(500, f"{type(e).__name__}: {e}")


class NewSession(BaseModel):
    case_id: str


class Message(BaseModel):
    text: str


@app.get("/api/health")
def health():
    return {"ok": True, "backend": BACKEND}


@app.get("/api/cases")
def cases(materia: str = "mpna"):
    return _call(session.list_cases, materia)


@app.post("/api/sessions")
def create_session(body: NewSession):
    return {"session_id": _call(session.new_session, body.case_id)}


@app.post("/api/sessions/{session_id}/messages")
def send_message(session_id: str, body: Message):
    if not body.text.strip():
        raise AgentError(400, "Mensaje vacío")
    return _call(session.send, session_id, body.text)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    return _call(session.get_session, session_id)


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str):
    return _call(session.finish, session_id)


@app.get("/api/rag/search")
def rag_search(q: str, materia: str = "mpna", k: int = Query(5, ge=1, le=30), tipo: str = ""):
    def _search():
        from rag.query import search
        return search(materia, q, k=k, tipo=tipo or None)
    results = _call(_search)
    return [{**r, "score": float(r["score"])} for r in results]


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
