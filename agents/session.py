"""Public interface of the simulator, used by the API and the frontend.

Contract (don't change it without updating api/):

    list_cases(materia) -> [{id, materia, titulo, dificultad, grillas, paciente: {nombre, edad, sexo}}]
    new_session(case_id, user=None, mode="chat") -> session_id     # user = {email, name}
    send(session_id, text, user=None) -> {
        "replies": [{"role": "paciente" | "docente", "text": str}],
        "debug": {"intent": str, "facts": [ids], "exams": [ids], "studies": [str],
                  "model": str, "latency_ms": int}
    }
    finish(session_id, user=None) -> get_session(...) with finished=True
    get_session(session_id, user=None) -> {
        "case_id": str, "transcript": [{"role": "estudiante" | "paciente" | "docente", "text": str}],
        "revealed_facts": [ids], "total_facts": int, "exams_done": [ids], "exams_done_labels": [str], "studies_requested": [str],
        "diagnosis_proposed": str | None, "finished": bool
    }

With a user, a consultation can only be read or continued by its owner (PermissionError otherwise).
"""

from agents.graph import finish, get_session, list_cases, new_session, send  # noqa: F401
