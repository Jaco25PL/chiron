// Chiron backend client (see agents/session.py for the contract).

// What the student may know before the consultation, as in the real exam: name and sex.
export type Paciente = { nombre: string; sexo: string };

export type Caso = {
  id: string;
  materia: string;
  paciente: Paciente;
};

export type Rol = "estudiante" | "paciente" | "docente";
export type Turno = { role: Rol; text: string };

export type Respuesta = {
  replies: { role: "paciente" | "docente"; text: string }[];
  debug: { intent: string; facts: string[]; exams: string[]; studies: string[]; latency_ms: number };
};

export type Resumen = {
  case: Caso;
  transcript: Turno[];
  revealed_facts: string[];
  total_facts: number;
  exams_done: string[];
  exams_done_labels: string[];
  studies_requested: string[];
  diagnosis_proposed: string | null;
  finished: boolean;
};

const SIN_BACKEND =
  "El servidor de casos no está disponible en este momento. En la versión online todavía no está desplegado; probalo en local.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error(SIN_BACKEND);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // An error without our {error} JSON means the backend itself didn't answer (not deployed / down).
    if (!body?.error && [404, 502, 503, 504].includes(res.status)) throw new Error(SIN_BACKEND);
    throw new Error(body?.error ?? `Error ${res.status}`);
  }
  return body as T;
}

export const api = {
  casos: (materia = "mpna") => call<Caso[]>(`/api/cases?materia=${materia}`),
  nuevaSesion: (caseId: string, mode: "chat" | "cara" = "chat") =>
    call<{ session_id: string; case: Caso }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, mode }),
    }),
  enviar: (sessionId: string, text: string) =>
    call<Respuesta>(`/api/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  terminar: (sessionId: string) => call<Resumen>(`/api/sessions/${sessionId}/finish`, { method: "POST" }),
  /** The patient's last reply as WAV audio. */
  voz: async (sessionId: string) => {
    const res = await fetch(`/api/sessions/${sessionId}/voz`, { method: "POST" });
    if (!res.ok) throw new Error(`Voz: error ${res.status}`);
    return res.arrayBuffer();
  },
};

export const ALEATORIO = "aleatorio";

export function sexoLabel(sexo: string) {
  return sexo === "femenino" ? "Paciente femenina" : "Paciente masculino";
}

export function iniciales(nombre: string) {
  return nombre
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("");
}
