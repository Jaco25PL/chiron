"""Public interface of the simulator, used by the API and the frontend.

Contract (don't change it without updating api/):

    list_cases(materia) -> [{id, materia, paciente: {nombre, sexo}}]   # id is opaque; see cases/catalog.py
    new_session(case_ref, user=None, mode="chat", nivel="normal") -> session_id
        # case_ref: public id, internal id or "aleatorio"; nivel: "normal" | "principiante" (ValueError otherwise)
    send(session_id, text, user=None) -> {
        "replies": [{"role": "paciente" | "docente", "text": str}],
        "debug": {"intent": str, "facts": [ids], "exams": [ids], "studies": [str],
                  "model": str, "latency_ms": int},
        "checklist": [...]                                         # only in "principiante", see below
    }
    speak(session_id, user=None) -> Iterator[bytes]                # the patient's last reply as 24 kHz PCM chunks
    finish(session_id, user=None) -> get_session(...) with finished=True and the feedback (computed once:
                                     calling it again returns the same one)
    get_session(session_id, user=None) -> {
        "case": {id, materia, paciente: {nombre, sexo}}, "transcript": [{"role": "estudiante" | "paciente" | "docente", "text": str}],
        "revealed_facts": [ids], "total_facts": int, "exams_done": [ids], "exams_done_labels": [str], "studies_requested": [str],
        "diagnosis_proposed": str | None, "finished": bool, "nivel": "normal" | "principiante",
        "checklist": [{"id": str, "texto": str, "tipo": "hecho" | "examen" | "estudio", "hecho": bool}],
        "feedback": None | {                                      # the docente's correction, once finished
            "score": int,                                         # 0-100 over the grilla, `global` excluded
            "parcial": bool,                                      # True: the LLM failed, coverage only
            "bien": [str], "falto": [str], "consejos": [str],     # never name the diagnosis
            "items": [{"id": str, "texto": str, "tipo": str,      # diagnostico/plan items: generic texto
                       "calificacion": "Excelente" | "Bien" | "Regular" | "No realizado" | None,
                       "evidencia": bool}]
        }
    }
    historial(user) -> [{"id": session_id, "fecha": iso str, "paciente": {nombre, sexo}, "modo": str,
                         "score": int, "para_la_proxima": [str]}]   # the user's finished consultations, newest first

"checklist" (agents/grilla.py checklist()) is present only when nivel is "principiante": in "normal"
the key is omitted, so the browser never receives the grilla. It never includes conduct, plan or
diagnosis items.

With a user, a consultation can only be read or continued by its owner (PermissionError otherwise).
"""

from agents.graph import finish, get_session, historial, list_cases, new_session, send, speak  # noqa: F401
