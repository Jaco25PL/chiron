"""Human review of the LLM judge (calibration), shown on the web app's /revision page.

Usage:
    python evals/review.py publicar [experiment]   # loads a sample of answers for review
    python evals/review.py reporte                 # judge vs reviewer agreement, per criterion

`publicar` takes the latest chiron-paciente experiment (or the one named), samples answers
stratified by category, and stores each one with what the reviewer needs to see (question,
answer, reference, the case's facts, the hidden diagnosis) and, apart, the verdict of the
judge and of the code evaluators. Needs DATABASE_URL (the deployed database) in .env.
Reviewers are the emails in CHIRON_REVIEWERS (env var of the chiron-api Vercel project).
"""

import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm import gemini  # noqa: E402,F401  (loads .env and the LangSmith project)
from langsmith import Client  # noqa: E402

from cases.catalog import load_case  # noqa: E402
from evals.datasets import PACIENTE  # noqa: E402
from store import review  # noqa: E402

# answers per category: ~30 in total, about 15 minutes for the reviewer
SAMPLE = {"hecho": 12, "inexistente": 5, "diagnostico": 5, "personaje": 4, "apertura": 3}
WITH_REFERENCE = ("hecho", "apertura")
SEED = 7


def criteria(categoria: str) -> list[str]:
    keys = ["no_revela_diagnostico", "sin_alucinaciones", "en_personaje"]
    return keys + (["consistente", "un_solo_hecho"] if categoria in WITH_REFERENCE else [])


def publicar(experiment: str | None) -> None:
    client = Client()
    if experiment is None:
        ds = client.read_dataset(dataset_name=PACIENTE)
        experiment = max(client.list_projects(reference_dataset_id=ds.id), key=lambda p: p.start_time).name
    runs = [r for r in client.list_runs(project_name=experiment, is_root=True) if r.outputs]
    feedback = defaultdict(dict)
    for f in client.list_feedback(run_ids=[r.id for r in runs]):
        feedback[str(f.run_id)][f.key] = {"score": f.score, "comentario": f.comment}
    examples = {str(e.id): e for e in client.list_examples(dataset_id=runs[0].reference_dataset_id)} if runs else {}

    by_cat = defaultdict(list)
    for r in runs:
        ref = examples[str(r.reference_example_id)].outputs
        by_cat[ref["categoria"]].append((r, ref))
    rng = random.Random(SEED)
    chosen = []
    for cat, n in SAMPLE.items():
        pool = sorted(by_cat[cat], key=lambda x: str(x[0].reference_example_id))
        # answers some evaluator failed always go in: they are the ones worth a second opinion
        failed = [x for x in pool if any(v["score"] == 0 for v in feedback[str(x[0].id)].values())]
        rest = [x for x in pool if x not in failed]
        chosen += failed + rng.sample(rest, max(0, min(n - len(failed), len(rest))))
    rng.shuffle(chosen)

    items = []
    for r, ref in chosen:
        case = load_case(r.inputs["case_id"])
        items.append({
            "id": str(r.reference_example_id)[:12],
            "item": {
                "paciente": " ".join(case["paciente"]["nombre"].split()[:2]),
                "diagnostico": case["diagnostico"]["principal"],
                "categoria": ref["categoria"],
                "pregunta": r.inputs["pregunta"],
                "respuesta": r.outputs["respuesta"],
                "referencia": ref.get("respuesta_referencia"),
                "hechos": [{"tema": h["tema"], "respuesta": h["respuesta"]} for h in case["anamnesis"]],
                "criterios": criteria(ref["categoria"]),
            },
            "juez": {"experimento": experiment, **feedback[str(r.id)]},
        })
    review.publish(items)
    print(f"{len(items)} answers from {experiment} published for review")


def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa between judge and reviewer; None when chance agreement is total (all one class)."""
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def reporte() -> None:
    rows = review.all_labels()
    print(f"{len({r['id'] for r in rows})} answers reviewed by {', '.join(sorted({r['reviewer'] for r in rows}))}\n")
    print("| criterion | labeled | agreement | judge fails | reviewer fails | kappa |")
    print("|---|---|---|---|---|---|")
    disagreements = []
    for c in review.CRITERIA:
        pairs = []
        for r in rows:
            human, judged = r["etiquetas"].get(c), r["juez"].get(c)
            if human is None or judged is None:
                continue
            pairs.append((bool(judged["score"]), human))
            if bool(judged["score"]) != human:
                disagreements.append((c, r))
        if not pairs:
            continue
        k = kappa(pairs)
        print(f"| {c} | {len(pairs)} | {sum(a == b for a, b in pairs)}/{len(pairs)} | {sum(not a for a, _ in pairs)} "
              f"| {sum(not b for _, b in pairs)} | {'n/a' if k is None else f'{k:.2f}'} |")
    print("\nDisagreements:")
    for c, r in disagreements:
        it = r["item"]
        print(f"\n- [{c}] judge={'pass' if r['juez'][c]['score'] else 'fail'}, reviewer={'pass' if r['etiquetas'][c] else 'fail'}")
        print(f"  {it['paciente']} · Q: {it['pregunta']}\n  A: {it['respuesta']}")
        if r["juez"][c].get("comentario"):
            print(f"  judge: {r['juez'][c]['comentario']}")
        if r["nota"]:
            print(f"  reviewer: {r['nota']}")
    notes = [r for r in rows if r["nota"] and not any(r is d for _, d in disagreements)]
    for r in notes:
        print(f"\n- note on \"{r['item']['pregunta']}\": {r['nota']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "publicar":
        publicar(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "reporte":
        reporte()
    else:
        sys.exit(__doc__)
