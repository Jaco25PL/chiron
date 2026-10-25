"""Human review of the LLM judge: a medical student labels the patient's eval answers.

`python evals/review.py publicar` loads a sample of answers from a LangSmith experiment;
the /revision page shows them to the reviewers listed in CHIRON_REVIEWERS, without the
judge's verdict (so it doesn't anchor them); `python evals/review.py reporte` compares
their labels with the judge.

With DATABASE_URL everything lives in Postgres (review_items, review_labels). Without it
(tests, the E2E fake backend) it lives in memory.
"""

import json
import os

# what the reviewer labels, in the order the page shows them
CRITERIA = ["no_revela_diagnostico", "sin_alucinaciones", "en_personaje", "consistente", "un_solo_hecho"]

_items: dict[str, dict] = {}  # in-memory fallback: id -> {"orden", "item", "juez"}
_labels: dict[tuple[str, str], dict] = {}  # (item_id, reviewer) -> {"etiquetas", "nota"}


def _db():
    if not os.environ.get("DATABASE_URL"):
        return None
    from store import db  # imported here: the CI fake backend has no database deps

    return db.pool()


def reviewers() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("CHIRON_REVIEWERS", "").split(",") if e.strip()}


def publish(items: list[dict]) -> None:
    """items: [{"id", "item", "juez"}] where `item` is what the reviewer sees (it must list its
    `criterios`) and `juez` the hidden verdict. Replaces the set; labels of kept ids survive."""
    pool = _db()
    if pool is None:
        _items.clear()
        _items.update({i["id"]: {"orden": n, "item": i["item"], "juez": i["juez"]} for n, i in enumerate(items)})
        return
    with pool.connection() as conn:
        conn.execute("DELETE FROM review_items WHERE NOT (id = ANY(%s))", ([i["id"] for i in items],))
        for n, i in enumerate(items):
            conn.execute(
                """INSERT INTO review_items (id, orden, item, juez) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET orden = EXCLUDED.orden, item = EXCLUDED.item, juez = EXCLUDED.juez""",
                (i["id"], n, json.dumps(i["item"]), json.dumps(i["juez"])),
            )


def items_for(reviewer: str) -> list[dict]:
    """What the page shows: every item with this reviewer's labels so far. Never the judge's verdict."""
    pool = _db()
    if pool is None:
        rows = [(k, v["item"], _labels.get((k, reviewer), {})) for k, v in sorted(_items.items(), key=lambda kv: kv[1]["orden"])]
    else:
        with pool.connection() as conn:
            found = conn.execute(
                """SELECT i.id, i.item, l.etiquetas, l.nota FROM review_items i
                   LEFT JOIN review_labels l ON l.item_id = i.id AND l.reviewer = %s ORDER BY i.orden""",
                (reviewer,),
            ).fetchall()
        rows = [(r[0], r[1], {"etiquetas": r[2] or {}, "nota": r[3] or ""}) for r in found]
    return [{"id": k, **item, "etiquetas": lab.get("etiquetas", {}), "nota": lab.get("nota", "")} for k, item, lab in rows]


def save(item_id: str, reviewer: str, etiquetas: dict[str, bool | None], nota: str) -> None:
    """Stores the reviewer's labels for one item. KeyError if the item doesn't exist."""
    pool = _db()
    if pool is None:
        if item_id not in _items:
            raise KeyError(item_id)
        _labels[(item_id, reviewer)] = {"etiquetas": etiquetas, "nota": nota}
        return
    with pool.connection() as conn:
        if not conn.execute("SELECT 1 FROM review_items WHERE id = %s", (item_id,)).fetchone():
            raise KeyError(item_id)
        conn.execute(
            """INSERT INTO review_labels (item_id, reviewer, etiquetas, nota) VALUES (%s, %s, %s, %s)
               ON CONFLICT (item_id, reviewer) DO UPDATE
               SET etiquetas = EXCLUDED.etiquetas, nota = EXCLUDED.nota, updated_at = now()""",
            (item_id, reviewer, json.dumps(etiquetas), nota),
        )


def all_labels() -> list[dict]:
    """Every item with the judge's verdict and every reviewer's labels, for the report."""
    pool = _db()
    if pool is None:
        return [{"id": k, "item": v["item"], "juez": v["juez"], "reviewer": r, **_labels[(k, r)]}
                for k, v in _items.items() for (i, r) in _labels if i == k]
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT i.id, i.item, i.juez, l.reviewer, l.etiquetas, l.nota FROM review_items i
               JOIN review_labels l ON l.item_id = i.id ORDER BY i.orden""",
        ).fetchall()
    return [{"id": r[0], "item": r[1], "juez": r[2], "reviewer": r[3], "etiquetas": r[4], "nota": r[5]} for r in rows]
