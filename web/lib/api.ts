// Cliente del backend de Chiron (ver agents/session.py para el contrato).

export type Paciente = { nombre: string; edad: number; sexo: string };

export type Caso = {
  id: string;
  materia: string;
  titulo: string;
  dificultad: "basico" | "intermedio" | "avanzado";
  grillas: string[];
  paciente: Paciente;
};

export type Rol = "estudiante" | "paciente" | "docente";
export type Turno = { role: Rol; text: string };

export type Respuesta = {
  replies: { role: "paciente" | "docente"; text: string }[];
  debug: { intent: string; facts: string[]; exams: string[]; studies: string[]; latency_ms: number };
};

export type Resumen = {
  case_id: string;
  transcript: Turno[];
  revealed_facts: string[];
  total_facts: number;
  exams_done: string[];
  exams_done_labels: string[];
  studies_requested: string[];
  diagnosis_proposed: string | null;
  finished: boolean;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error("No hay conexión con el servidor de Chiron. ¿Está corriendo el backend en el puerto 8000?");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ?? `Error ${res.status}`);
  return body as T;
}

export const api = {
  casos: (materia = "mpna") => call<Caso[]>(`/api/cases?materia=${materia}`),
  nuevaSesion: (caseId: string) =>
    call<{ session_id: string }>("/api/sessions", { method: "POST", body: JSON.stringify({ case_id: caseId }) }),
  enviar: (sessionId: string, text: string) =>
    call<Respuesta>(`/api/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  terminar: (sessionId: string) => call<Resumen>(`/api/sessions/${sessionId}/finish`, { method: "POST" }),
};

export const DIFICULTAD: Record<Caso["dificultad"], string> = {
  basico: "Básico",
  intermedio: "Intermedio",
  avanzado: "Avanzado",
};

export function iniciales(nombre: string) {
  return nombre
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("");
}
