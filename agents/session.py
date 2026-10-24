"""Interfaz pública del simulador para la API y el front.

Contrato (no cambiar sin actualizar api/):

    list_cases(materia) -> [{id, materia, titulo, dificultad, grillas, paciente: {nombre, edad, sexo}}]
    new_session(case_id) -> session_id
    send(session_id, text) -> {
        "replies": [{"role": "paciente" | "docente", "text": str}],
        "debug": {"intent": str, "facts": [ids], "exams": [ids], "studies": [str],
                  "model": str, "latency_ms": int}
    }
    finish(session_id) -> get_session(...) con finished=True
    get_session(session_id) -> {
        "case_id": str, "transcript": [{"role": "estudiante" | "paciente" | "docente", "text": str}],
        "revealed_facts": [ids], "total_facts": int, "exams_done": [ids], "studies_requested": [str],
        "diagnosis_proposed": str | None, "finished": bool
    }
"""

from agents.graph import finish, get_session, list_cases, new_session, send  # noqa: F401
