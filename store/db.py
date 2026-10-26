"""Persistence: users, consultations and turns in Postgres (Neon), plus the LangGraph checkpointer.

Everything is optional: without DATABASE_URL the app keeps consultations in memory
(local development), and the functions here become no-ops.
"""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # the CI fake backend installs only fastapi + uvicorn (and has no database)
    pass

SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@lru_cache
def pool():
    from psycopg_pool import ConnectionPool

    # prepare_threshold=None: Neon's pooled endpoint (PgBouncer) doesn't support prepared statements.
    # Neon closes idle connections, and the function outlives them: check each connection before
    # handing it out (a dead one is replaced) and drop idle ones first ("SSL connection has been
    # closed unexpectedly" on the first query after a quiet spell).
    p = ConnectionPool(
        os.environ["DATABASE_URL"],
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": None},
        check=ConnectionPool.check_connection,
        max_idle=120,
        open=True,
    )
    with p.connection() as conn:
        conn.execute(SCHEMA)
    return p


def checkpointer():
    """Where LangGraph keeps each consultation's state: Postgres if available, else memory."""
    if not enabled():
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver

    saver = PostgresSaver(pool())
    saver.setup()  # creates/migrates the checkpoint tables
    return saver


def upsert_user(email: str, name: str | None) -> int | None:
    if not enabled():
        return None
    with pool().connection() as conn:
        row = conn.execute(
            """INSERT INTO users (email, name) VALUES (%s, %s)
               ON CONFLICT (email) DO UPDATE SET name = COALESCE(EXCLUDED.name, users.name), last_seen = now()
               RETURNING id""",
            (email, name),
        ).fetchone()
    return row[0]


def create_consultation(consultation_id: str, user_id: int | None, case_id: str, mode: str,
                        nivel: str = "normal") -> None:
    if not enabled() or user_id is None:
        return
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO consultations (id, user_id, case_id, mode, nivel) VALUES (%s, %s, %s, %s, %s)",
            (consultation_id, user_id, case_id, mode, nivel),
        )


def add_turns(consultation_id: str, first_n: int, turns: list[dict]) -> None:
    """turns: [{role, text, intent?, facts?, exams?, studies?, latency_ms?, timings?}] numbered from first_n."""
    if not enabled() or not turns:
        return
    rows = [
        (consultation_id, first_n + i, t["role"], t["text"], t.get("intent"), t.get("facts"),
         t.get("exams"), t.get("studies"), t.get("latency_ms"),
         json.dumps(t["timings"]) if t.get("timings") else None)
        for i, t in enumerate(turns)
    ]
    with pool().connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO turns (consultation_id, n, role, text, intent, facts, exams, studies, latency_ms, timings)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            rows,
        )


# Without a database: the feedback of finished consultations, so local dev still has a history.
_memory_feedback: dict[str, dict] = {}


def save_feedback(consultation_id: str, feedback: dict, *, owner: str, case_id: str, mode: str,
                  nivel: str = "normal") -> None:
    """Stores the docente's feedback once (a second call keeps the first). owner, case_id, mode and nivel
    are only used in memory: in Postgres they are already in `consultations`."""
    if not enabled():
        if owner:
            _memory_feedback.setdefault(consultation_id, {
                "id": consultation_id, "owner": owner, "case_id": case_id, "mode": mode,
                "nivel": nivel, "score": feedback["score"], "resultado": feedback,
                "fecha": datetime.now(timezone.utc).isoformat(),
            })
        return
    with pool().connection() as conn:
        # consultations without an owner (no user) have no row: nothing to attach the feedback to
        conn.execute(
            """INSERT INTO feedback (consultation_id, score, resultado)
               SELECT %s, %s, %s WHERE EXISTS (SELECT 1 FROM consultations WHERE id = %s)
               ON CONFLICT (consultation_id) DO NOTHING""",
            (consultation_id, feedback["score"], json.dumps(feedback), consultation_id),
        )


def history(email: str) -> list[dict]:
    """The user's finished consultations with feedback, newest first:
    [{id, fecha, case_id, mode, nivel, score, resultado}]."""
    if not enabled():
        rows = [r for r in _memory_feedback.values() if r["owner"] == email]
        return sorted(({k: v for k, v in r.items() if k != "owner"} for r in rows),
                      key=lambda r: r["fecha"], reverse=True)
    with pool().connection() as conn:
        rows = conn.execute(
            """SELECT c.id, COALESCE(c.finished_at, f.created_at) AS fecha, c.case_id, c.mode, f.score, f.resultado,
                      c.nivel
               FROM consultations c JOIN feedback f ON f.consultation_id = c.id JOIN users u ON u.id = c.user_id
               WHERE u.email = %s ORDER BY fecha DESC LIMIT 200""",
            (email,),
        ).fetchall()
    return [{"id": r[0], "fecha": r[1].isoformat(), "case_id": r[2], "mode": r[3], "score": r[4],
             "resultado": r[5] if isinstance(r[5], dict) else json.loads(r[5]), "nivel": r[6]} for r in rows]


def finish_consultation(consultation_id: str) -> None:
    if not enabled():
        return
    with pool().connection() as conn:
        conn.execute(
            "UPDATE consultations SET finished_at = COALESCE(finished_at, now()) WHERE id = %s",
            (consultation_id,),
        )


# --- Per-user preferences ---------------------------------------------------------------

ACENTOS = ("menta", "rosa", "gris", "azul")  # accent colors offered in the user menu
_acentos: dict[str, str] = {}  # in-memory fallback without DATABASE_URL: email -> acento


def get_acento(email: str) -> str:
    if not enabled():
        return _acentos.get(email, ACENTOS[0])
    with pool().connection() as conn:
        row = conn.execute("SELECT acento FROM users WHERE email = %s", (email,)).fetchone()
    return row[0] if row else ACENTOS[0]


def set_acento(email: str, name: str | None, acento: str) -> None:
    """Saves the user's accent color, creating the user if this is their first request."""
    if acento not in ACENTOS:
        raise ValueError(f"unknown accent: {acento!r}")
    if not enabled():
        _acentos[email] = acento
        return
    with pool().connection() as conn:
        conn.execute(
            """INSERT INTO users (email, name, acento) VALUES (%s, %s, %s)
               ON CONFLICT (email) DO UPDATE SET acento = EXCLUDED.acento,
                   name = COALESCE(EXCLUDED.name, users.name), last_seen = now()""",
            (email, name, acento),
        )


# --- Gemini spend on the paid key ------------------------------------------------------------

_memory_spend: dict[str, float] = {}  # in-memory fallback without DATABASE_URL: month -> USD


def add_gemini_spend(month: str, usd: float) -> float:
    """Adds to the month's spend on the paid Gemini key and returns the month's total."""
    if not enabled():
        _memory_spend[month] = _memory_spend.get(month, 0.0) + usd
        return _memory_spend[month]
    with pool().connection() as conn:
        row = conn.execute(
            """INSERT INTO gemini_spend (month, usd) VALUES (%s, %s)
               ON CONFLICT (month) DO UPDATE SET usd = gemini_spend.usd + EXCLUDED.usd RETURNING usd""",
            (month, usd),
        ).fetchone()
    return float(row[0])


def gemini_spend(month: str) -> float:
    if not enabled():
        return _memory_spend.get(month, 0.0)
    with pool().connection() as conn:
        row = conn.execute("SELECT usd FROM gemini_spend WHERE month = %s", (month,)).fetchone()
    return float(row[0]) if row else 0.0
