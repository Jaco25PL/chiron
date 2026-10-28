// Chiron backend client (see agents/session.py for the contract).

import type { Acento } from "@/lib/acento";
import type { MascotaId } from "@/lib/mascotas";

// What the student may know before the consultation, as in the real exam: name and sex.
export type Paciente = { nombre: string; sexo: string };

export type Caso = {
  id: string;
  materia: string;
  paciente: Paciente;
};

export type Rol = "estudiante" | "paciente" | "docente";
export type Turno = { role: Rol; text: string };

/** "principiante" shows the grilla checklist during the consultation; the patient is the same. */
export type Nivel = "principiante" | "normal";

/** A grilla item the student must not forget, ticked by the backend once covered (beginner level only).
 *  tipo: hecho = ask the patient, examen = physical exam, estudio = order a study. */
export type ItemChecklist = {
  id: string;
  texto: string;
  tipo: "hecho" | "examen" | "estudio";
  seccion: string; // the grilla section, as on the paper grilla ("Fenómenos acompañantes"…)
  hecho: boolean;
};

export type Respuesta = {
  replies: { role: "paciente" | "docente"; text: string }[];
  debug: { intent: string; facts: string[]; exams: string[]; studies: string[]; latency_ms: number };
  checklist?: ItemChecklist[]; // only in "principiante"
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
  nivel: Nivel;
  checklist?: ItemChecklist[]; // only in "principiante"
  feedback: Feedback | null;
};

/** The grilla scale; null = not rated (the docente's LLM failed and the app can't judge that item). */
export type Calificacion = "Excelente" | "Bien" | "Regular" | "No realizado";

/** One grilla item as the student sees it: diagnosis and plan items carry a generic texto. */
export type ItemGrilla = {
  id: string;
  texto: string;
  tipo: "hecho" | "examen" | "estudio" | "conducta" | "plan" | "diagnostico" | "global";
  calificacion: Calificacion | null;
  evidencia: boolean;
};

/** The docente's correction when the consultation ends. Never names the diagnosis. */
export type Feedback = {
  score: number; // 0-100, "global" items excluded
  parcial: boolean; // the docente's LLM failed: coverage only, no tips
  bien: string[];
  falto: string[];
  consejos: string[];
  items: ItemGrilla[];
  tutor_consultas?: number; // "normal" only: how many times the student asked the study companion
};

/** The study companion's answer, from the course material. */
export type RespuestaTutor = {
  texto: string;
  fuentes: { tipo: string | null; fuente: string | null; seccion: string | null; pagina: number | null }[];
};

export type Preferencias = { acento: Acento; mascota: MascotaId };

/** A finished consultation in the student's history (newest first). */
export type ConsultaPasada = {
  id: string;
  fecha: string; // ISO
  paciente: Paciente;
  modo: string;
  nivel: Nivel;
  score: number;
  para_la_proxima: string[];
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
  nuevaSesion: (caseId: string, mode: "chat" | "cara" = "chat", nivel: Nivel = "normal") =>
    call<{ session_id: string; case: Caso; checklist?: ItemChecklist[] }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, mode, nivel }),
    }),
  enviar: (sessionId: string, text: string) =>
    call<Respuesta>(`/api/sessions/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  /** Ends the consultation; the docente's correction (one LLM call) can take several seconds. */
  terminar: (sessionId: string) => call<Resumen>(`/api/sessions/${sessionId}/finish`, { method: "POST" }),
  historial: () => call<ConsultaPasada[]>("/api/historial"),
  preferencias: () => call<Preferencias>("/api/preferencias"),
  guardarAcento: (acento: Acento) =>
    call<Preferencias>("/api/preferencias", { method: "POST", body: JSON.stringify({ acento }) }),
  guardarMascota: (mascota: MascotaId) =>
    call<Preferencias>("/api/preferencias", { method: "POST", body: JSON.stringify({ mascota }) }),
  /** Face-to-face call: the reply arrives first (onRespuesta) and then the patient's voice, as 24 kHz
   *  16-bit PCM chunks while it is generated (onAudio). Resolves when the voice has fully arrived. */
  enviarConVoz: (
    sessionId: string,
    text: string,
    { onRespuesta, onAudio }: { onRespuesta: (r: Respuesta) => void; onAudio: (pcm: ArrayBuffer) => void },
  ) => conVoz(`/api/sessions/${sessionId}/messages?voz=1`, text, "respuesta", onRespuesta, onAudio),
  /** A question to the study companion (not a consultation turn: the patient doesn't hear it). */
  tutor: (sessionId: string, text: string) =>
    call<RespuestaTutor>(`/api/sessions/${sessionId}/tutor`, { method: "POST", body: JSON.stringify({ text }) }),
  /** The same, answered out loud: the text first, then its voice in chunks (like enviarConVoz). */
  tutorConVoz: (
    sessionId: string,
    text: string,
    { onRespuesta, onAudio }: { onRespuesta: (r: RespuestaTutor) => void; onAudio: (pcm: ArrayBuffer) => void },
  ) => conVoz(`/api/sessions/${sessionId}/tutor?voz=1`, text, "tutor", onRespuesta, onAudio),
};

/** Reads an NDJSON voice stream: one `primera` line with the text, then base64 PCM `audio` lines.
 *  Resolves when the voice has fully arrived. */
async function conVoz<T>(
  url: string,
  text: string,
  primera: string,
  onRespuesta: (r: T) => void,
  onAudio: (pcm: ArrayBuffer) => void,
) {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new Error(SIN_BACKEND);
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error ?? SIN_BACKEND);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  let audios = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += value;
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const linea = JSON.parse(buf.slice(0, i));
      buf = buf.slice(i + 1);
      if (linea.tipo === primera) onRespuesta(linea as T);
      else if (linea.tipo === "audio") {
        audios++;
        onAudio(Uint8Array.from(atob(linea.pcm), (c) => c.charCodeAt(0)).buffer);
      } else if (linea.tipo === "error") {
        // the voice already played (it broke near the end): no need to alarm the student
        if (audios) console.warn("voz:", linea.error);
        else throw new Error(`Voz: ${linea.error}`);
      }
    }
  }
}

/** One patient answer from the evals, for the medical reviewer to label (/revision). */
export type ItemRevision = {
  id: string;
  paciente: string;
  diagnostico: string;
  categoria: "hecho" | "apertura" | "diagnostico" | "inexistente" | "personaje";
  pregunta: string;
  respuesta: string;
  referencia: string | null;
  hechos: { tema: string; respuesta: string }[];
  criterios: string[];
  etiquetas: Record<string, boolean | null>;
  nota: string;
};

export const revision = {
  items: () => call<{ criterios: string[]; items: ItemRevision[] }>("/api/revision"),
  guardar: (id: string, etiquetas: ItemRevision["etiquetas"], nota: string) =>
    call<{ ok: true }>(`/api/revision/${id}`, { method: "POST", body: JSON.stringify({ etiquetas, nota }) }),
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
