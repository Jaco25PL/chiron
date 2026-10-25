"""Corre los evals contra LangSmith y deja los resultados como experimentos.

Uso:
    python evals/datasets.py         # una vez, o cuando cambian los casos
    python evals/run.py              # paciente + router
    python evals/run.py router       # solo el router

Evaluadores del paciente:
- no_revela_diagnostico   (juez LLM)  nunca dice ni insinúa el diagnóstico
- sin_alucinaciones       (juez LLM)  no inventa síntomas, antecedentes ni datos fuera del caso
- en_personaje            (juez LLM)  habla como paciente: sin jerga médica, no es "una IA"
- consistente             (juez LLM)  coincide con el hecho de referencia (categoría hecho/apertura)
- hecho_correcto          (código)    el hecho que el modelo dice haber usado es el esperado
- un_solo_hecho           (código)    no revela más de un hecho por pregunta
Evaluador del router:
- intent_correcto         (código)    la intención coincide con la esperada
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langsmith import evaluate  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agents import graph  # noqa: E402
from evals.datasets import PACIENTE, ROUTER  # noqa: E402
from llm.gemini import MODELS, chat_model  # noqa: E402

# --- targets: qué se evalúa ----------------------------------------------------


def paciente_target(inputs: dict) -> dict:
    """Una pregunta suelta al paciente (sin historia previa), usando el nodo real del grafo."""
    state = {"case_id": inputs["case_id"], "transcript": [{"role": "estudiante", "text": inputs["pregunta"]}]}
    out = graph.paciente(state)
    return {"respuesta": out["transcript"][0]["text"], "hechos_usados": out["debug"]["facts"]}


def router_target(inputs: dict) -> dict:
    state = {"transcript": [{"role": "estudiante", "text": inputs["mensaje"]}]}
    return {"intent": graph.router(state)["intent"]}


# --- juez LLM ---------------------------------------------------------------------


class Veredicto(BaseModel):
    no_revela_diagnostico: bool = Field(description="True si NO nombra ni insinúa el diagnóstico oculto")
    sin_alucinaciones: bool = Field(description="True si no inventa síntomas, antecedentes o datos clínicos ausentes del caso")
    en_personaje: bool = Field(description="True si habla como paciente: lenguaje cotidiano, sin jerga médica, no admite ser una IA ni da consejos médicos")
    consistente: bool = Field(description="True si el contenido coincide con la respuesta de referencia (si no hay referencia, True)")
    comentario: str = Field(description="Una oración justificando cualquier False")


JUEZ = """Sos un evaluador estricto de un simulador de pacientes para el ECOE (examen clínico práctico).
Un estudiante le hizo una pregunta a un paciente simulado por IA. Evaluá la respuesta del paciente.

Caso clínico (lo que el paciente sabe y puede revelar si se lo preguntan):
{hechos}

Diagnóstico OCULTO (el paciente nunca debe decirlo ni insinuarlo): {diagnostico}

Pregunta del estudiante: {pregunta}
Respuesta del paciente: {respuesta}
Respuesta de referencia (si existe): {referencia}

Criterios:
- no_revela_diagnostico: falla si nombra el diagnóstico, un sinónimo o una pista inequívoca. Que el paciente nombre \
sus enfermedades ya conocidas (p. ej. "tengo diabetes", "soy hipertenso") NO es revelar el diagnóstico.
- sin_alucinaciones: falla si afirma un síntoma, antecedente o dato clínico que no está en el caso. Negar algo que \
no está en el caso es correcto. Detalles cotidianos irrelevantes (el nombre del perro) no cuentan.
- en_personaje: falla si usa términos técnicos que un paciente no usaría, si admite ser una IA o si da \
recomendaciones médicas.
- consistente: falla si contradice la respuesta de referencia u omite su contenido central."""


_judge = None


def judge(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    global _judge
    _judge = _judge or chat_model("judge", Veredicto, thinking_level="low")
    case = graph.load_case(inputs["case_id"])
    hechos = "\n".join(f"- {h['tema']}: {h['respuesta']}" for h in case["anamnesis"])
    prompt = JUEZ.format(
        hechos=hechos,
        diagnostico=case["diagnostico"]["principal"],
        pregunta=inputs["pregunta"],
        respuesta=outputs["respuesta"],
        referencia=reference_outputs.get("respuesta_referencia", "(sin referencia)"),
    )
    v = _judge.invoke([SystemMessage(prompt), HumanMessage("Evaluá.")])
    keys = ["no_revela_diagnostico", "sin_alucinaciones", "en_personaje"]
    if reference_outputs["categoria"] in ("hecho", "apertura"):
        keys.append("consistente")
    return {"results": [{"key": k, "score": int(getattr(v, k)), "comment": v.comentario} for k in keys]}


# --- evaluadores de código --------------------------------------------------------


# Devuelven {"results": []} cuando el ejemplo no es de la categoría que miden.
def hecho_correcto(outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs["categoria"] != "hecho":
        return {"results": []}
    return {"key": "hecho_correcto", "score": int(reference_outputs["hecho_esperado"] in outputs["hechos_usados"])}


def un_solo_hecho(outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs["categoria"] not in ("hecho", "apertura"):
        return {"results": []}
    return {"key": "un_solo_hecho", "score": int(len(outputs["hechos_usados"]) <= 1)}


def intent_correcto(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "intent_correcto", "score": int(outputs["intent"] == reference_outputs["intent"])}


def main():
    which = sys.argv[1:] or ["paciente", "router"]
    if "router" in which:
        evaluate(
            router_target, data=ROUTER, evaluators=[intent_correcto],
            experiment_prefix=f"router-{MODELS['router'][0]}", max_concurrency=4,
            metadata={"modelo": MODELS["router"][0]},
        )
    if "paciente" in which:
        evaluate(
            paciente_target, data=PACIENTE, evaluators=[judge, hecho_correcto, un_solo_hecho],
            experiment_prefix=f"paciente-{MODELS['patient'][0]}", max_concurrency=2,
            metadata={"modelo_paciente": MODELS["patient"][0], "modelo_juez": MODELS["judge"][0]},
        )


if __name__ == "__main__":
    main()
