"""Persistence: users, consultations and turns in Postgres (Neon), plus the LangGraph checkpointer.

Everything is optional: without DATABASE_URL the app keeps consultations in memory
(local development), and the functions here become no-ops.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@lru_cache
def pool():
    from psycopg_pool import ConnectionPool

    # prepare_threshold=None: Neon's pooled endpoint (PgBouncer) doesn't support prepared statements
    p = ConnectionPool(
        os.environ["DATABASE_URL"],
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": None},
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


def create_consultation(consultation_id: str, user_id: int | None, case_id: str, mode: str) -> None:
    if not enabled() or user_id is None:
        return
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO consultations (id, user_id, case_id, mode) VALUES (%s, %s, %s, %s)",
            (consultation_id, user_id, case_id, mode),
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


def finish_consultation(consultation_id: str) -> None:
    if not enabled():
        return
    with pool().connection() as conn:
        conn.execute(
            "UPDATE consultations SET finished_at = COALESCE(finished_at, now()) WHERE id = %s",
            (consultation_id,),
        )
