"""Public interface of the simulator, used by the API and the frontend.

Contract (don't change it without updating api/):

    list_cases(materia) -> [{id, materia, paciente: {nombre, sexo}}]   # id is opaque; see cases/catalog.py
    new_session(case_ref, user=None, mode="chat") -> session_id     # public id, internal id or "aleatorio"
    send(session_id, text, user=None) -> {
        "replies": [{"role": "paciente" | "docente", "text": str}],
        "debug": {"intent": str, "facts": [ids], "exams": [ids], "studies": [str],
                  "model": str, "latency_ms": int}
    }
    speak(session_id, user=None) -> Iterator[bytes]                # the patient's last reply as 24 kHz PCM chunks
    finish(session_id, user=None) -> get_session(...) with finished=True
    get_session(session_id, user=None) -> {
        "case": {id, materia, paciente: {nombre, sexo}}, "transcript": [{"role": "estudiante" | "paciente" | "docente", "text": str}],
        "revealed_facts": [ids], "total_facts": int, "exams_done": [ids], "exams_done_labels": [str], "studies_requested": [str],
        "diagnosis_proposed": str | None, "finished": bool
    }

With a user, a consultation can only be read or continued by its owner (PermissionError otherwise).
"""

from agents.graph import finish, get_session, list_cases, new_session, send, speak  # noqa: F401
