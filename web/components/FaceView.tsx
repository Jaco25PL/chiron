"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { type Caso, type Turno } from "@/lib/api";
import { type MascotaId, mascota } from "@/lib/mascotas";
import type { CharlaTutor, ConVoz, ConVozTutor } from "@/lib/useConsulta";
import { ASCII_FACE } from "@/lib/ascii-face";
import { palabras, useEscucha, useVozPaciente } from "@/lib/voz";
import { CameraOff, Close, Mic, Phone, PhoneDown, Stethoscope } from "./icons";
import { Mascota } from "./Mascota";
import { TextoEscrito } from "./TextoEscrito";

// three.js only downloads when face to face opens; the ASCII portrait covers the wait
const Avatar3D = dynamic(() => import("./Avatar3D"), { ssr: false });
const AVATAR = "/avatares/generico.vrm"; // generic for now; one per patient later
// A real video call has no captions of the other person: the patient is only heard. Their line stays in
// the page for screen readers (sr-only); true shows it on screen again. The student's own words still show.
const SUBTITULOS_PACIENTE = false;

/** The waiting ASCII portrait: public/retratos/<id>.txt for the case, else the default one (built in). */
function useRetrato(caseId: string | undefined) {
  const [arte, setArte] = useState(ASCII_FACE);
  useEffect(() => {
    if (!caseId) return;
    const leer = (f: string) => fetch(`/retratos/${f}.txt`).then((r) => (r.ok ? r.text() : null));
    leer(caseId)
      .then((t) => t ?? leer("default"))
      .then((t) => t && setArte(t.replace(/\s+$/, "")))
      .catch(() => {});
  }, [caseId]);
  const lineas = arte.split("\n");
  const cols = Math.max(...lineas.map((l) => l.length));
  return { arte, cols, filas: lineas.length };
}

/** "Face to face" view: a voice call with the patient, like the voice mode of ChatGPT or Claude.
 *  Two buttons only: answer and hang up. Once answered the microphone stays open; each phrase is sent
 *  when the student pauses, the patient answers out loud (Gemini TTS), and talking over the patient
 *  interrupts them. Exams and studies are asked for by voice too. Tapping the study companion's pet
 *  sends the next phrase to it instead (the patient doesn't hear it and the clock stops); it answers in
 *  its own voice and the call goes back to the patient by itself. */
export function FaceView({
  caso,
  turnos,
  pensando,
  listo,
  onSend,
  onEnd,
  tutor,
}: {
  caso: Caso | null;
  turnos: Turno[];
  pensando: boolean;
  listo: boolean;
  onSend: (t: string, voz: ConVoz) => void;
  onEnd: () => void;
  tutor: {
    mascotaId: MascotaId;
    charla: CharlaTutor[];
    pensando: boolean;
    onPreguntar: (t: string, voz: ConVozTutor) => void;
    pausar: (si: boolean) => void;
  };
}) {
  const router = useRouter();
  const ultimoPaciente = [...turnos].reverse().find((t) => t.role === "paciente");
  const ultimoIdx = turnos.length - 1;
  const ultimoDocente = turnos[ultimoIdx]?.role === "docente" ? turnos[ultimoIdx] : null;
  const [cerrado, setCerrado] = useState<number | null>(null);
  const nombre = caso?.paciente.nombre.split(" ").slice(0, 2).join(" ") ?? "Paciente";
  const { arte, cols, filas } = useRetrato(caso?.id);

  const voz = useVozPaciente();
  const { callar, hablar } = voz;
  // who the voice belongs to: the avatar only moves its mouth for the patient
  const [vozDe, setVozDe] = useState<"paciente" | "tutor">("paciente");
  // talking to the study companion: the next phrase goes to it, not to the patient
  const [conTutor, setConTutor] = useState(false);
  const conTutorRef = useRef(false);
  // the student already asked in this round with the companion: "Te escucho" gives way to its answer
  const [pregunto, setPregunto] = useState(false);
  // its answer stays readable for a while after the call goes back to the patient
  const [ultimaVisible, setUltimaVisible] = useState(false);
  const ocultarUltima = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { pausar, onPreguntar } = tutor;
  const nombreTutor = mascota(tutor.mascotaId).nombre;
  const ultimaTutor = tutor.charla.at(-1)?.respuesta?.texto;

  // the patient's voice can come back through the speakers: what is heard while (or right after)
  // they speak, made of their own words, is echo and neither interrupts nor gets sent
  const sonando = useRef({ hablando: false, texto: "", hasta: 0 });
  useEffect(() => {
    if (sonando.current.hablando && !voz.hablando) sonando.current.hasta = Date.now();
    sonando.current.hablando = voz.hablando;
  }, [voz.hablando]);
  // Stricter than it looks necessary: speech recognition garbles the echo, so it rarely matches the
  // patient's words exactly (a 60% match let echoes through: they cut the patient off and were sent as
  // the student's words). While the patient talks, short fragments are ignored too.
  const esEco = useCallback((t: string) => {
    const s = sonando.current;
    if (!s.hablando && Date.now() - s.hasta > 2000) return false;
    const oidas = palabras(t);
    if (s.hablando && oidas.length < 3) return true;
    const dichas = new Set(palabras(s.texto));
    return !oidas.length || oidas.filter((w) => dichas.has(w)).length / oidas.length >= 0.3;
  }, []);

  // each phrase goes with its reply's voice: the text arrives first, then the audio streams in and
  // plays as it arrives. Only the patient speaks; the docente's reports stay on the card.
  const decir = useCallback(
    (t: string) => {
      let voces: ReturnType<typeof hablar> | null = null;
      onSend(t, {
        alResponder: (replies) => {
          const paciente = replies.findLast((r) => r.role === "paciente");
          if (!paciente) return;
          sonando.current.texto = paciente.text; // before the audio, so its echo is recognized
          setVozDe("paciente");
          voces = hablar();
        },
        alAudio: (pcm) => voces?.encolar(pcm),
        alTerminar: () => voces?.terminar(),
      });
    },
    [onSend, hablar],
  );

  /** Back to the patient: the clock runs again. */
  const volverAlPaciente = useCallback(() => {
    conTutorRef.current = false;
    setConTutor(false);
    pausar(false);
    if (ocultarUltima.current) clearTimeout(ocultarUltima.current);
    ocultarUltima.current = setTimeout(() => setUltimaVisible(false), 7000);
  }, [pausar]);
  useEffect(() => () => void (ocultarUltima.current && clearTimeout(ocultarUltima.current)), []);

  // the question goes to the companion; once its answer has been heard, back to the patient
  const decirTutor = useCallback(
    (t: string) => {
      let voces: ReturnType<typeof hablar> | null = null;
      setPregunto(true);
      onPreguntar(t, {
        alResponder: (r) => {
          sonando.current.texto = r.texto;
          setVozDe("tutor");
          setUltimaVisible(true);
          voces = hablar(volverAlPaciente);
        },
        alAudio: (pcm) => voces?.encolar(pcm),
        alTerminar: () => voces?.terminar(),
      });
    },
    [onPreguntar, hablar, volverAlPaciente],
  );

  const tocarMascota = () => {
    if (conTutorRef.current) {
      if (vozDe === "tutor") callar();
      volverAlPaciente();
      return;
    }
    callar(); // the patient stops talking: the student is asking for help
    setPregunto(false);
    setUltimaVisible(false);
    conTutorRef.current = true;
    setConTutor(true);
    pausar(true);
  };

  // a phrase finished while the patient is still "thinking" waits and goes right after
  const pendiente = useRef("");
  const ocupado = useRef(pensando);
  useEffect(() => {
    ocupado.current = pensando;
    if (!pensando && pendiente.current) {
      const t = pendiente.current;
      pendiente.current = "";
      decir(t);
    }
  }, [pensando, decir]);

  const escucha = useEscucha({
    onFrase: (t) => {
      if (conTutorRef.current) {
        if (!tutor.pensando) decirTutor(t);
      } else if (ocupado.current) pendiente.current = `${pendiente.current} ${t}`.trim();
      else decir(t);
    },
    onVoz: (t) => {
      if (!conTutorRef.current) setUltimaVisible(false); // back to the patient: the old answer goes
      // the student talks over the patient: a real sentence, not a stray word (that's usually echo)
      if (sonando.current.hablando && palabras(t).length >= 4) callar();
    },
    esEco,
  });

  const idxPaciente = ultimoPaciente ? turnos.lastIndexOf(ultimoPaciente) : -1;

  const contestar = () => {
    voz.desbloquear(); // inside the tap: iOS only allows audio after a gesture
    escucha.contestar();
  };
  const cortar = () => {
    escucha.colgar();
    callar();
    if (conTutorRef.current) volverAlPaciente();
    if (turnos.length)
      onEnd(); // ends the consultation and shows the summary
    else router.push("/"); // declined before saying anything
  };

  const enLlamada = escucha.activa;
  const [avatar, setAvatar] = useState<"cargando" | "listo" | "error">("cargando");
  const conAvatar = avatar === "listo";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 pb-[max(12px,env(safe-area-inset-bottom))] sm:px-6">
      {/* escenario */}
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-[28px] border border-line bg-[radial-gradient(ellipse_at_50%_35%,var(--accent-fondo)_0%,var(--bg)_70%)] [container-type:size]">
        {avatar !== "error" && (
          <div
            role="img"
            aria-label={conAvatar ? `Retrato de ${nombre}` : undefined}
            aria-hidden={!conAvatar}
            className={`absolute inset-0 transition-opacity duration-300 ease-out ${
              conAvatar ? (enLlamada ? "opacity-100" : "opacity-40") : "opacity-0"
            }`}
          >
            <Avatar3D
              url={AVATAR}
              analyser={voz.analyser}
              hablando={voz.hablando && vozDe === "paciente"}
              onListo={() => setAvatar("listo")}
              onError={() => setAvatar("error")}
              className="size-full"
            />
          </div>
        )}
        {!conAvatar && (
          <pre
            aria-label={`Retrato de ${nombre}`}
            className={`pointer-events-none absolute left-1/2 top-[52%] -translate-x-1/2 -translate-y-1/2 select-none font-mono leading-none transition-opacity duration-300 ease-out [mask-image:radial-gradient(ellipse_70%_75%_at_50%_45%,#000_55%,transparent_100%)] ${
              enLlamada ? "opacity-100" : "opacity-35"
            }`}
            style={{
              // a monospace character is ~0.6em wide. Height drives the size; on narrow (mobile) screens
              // the shoulders may overflow the sides so the face stays large
              fontSize: `min(calc(150cqw / ${cols * 0.6}), calc(90cqh / ${filas}))`,
              backgroundImage:
                "linear-gradient(180deg,var(--accent-claro) 0%,var(--accent) 45%,var(--accent-oscuro) 100%)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            {arte}
          </pre>
        )}
        {/* líneas de barrido fijas, solo sobre el retrato ASCII */}
        {!conAvatar && (
          <div className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(0deg,rgb(0_0_0/0.18)_0px,rgb(0_0_0/0.18)_1px,transparent_1px,transparent_3px)]" />
        )}

        {/* propia cámara: muestra si el micrófono está abierto */}
        <div className="glass absolute right-3 top-3 grid aspect-[3/4] w-[22%] max-w-36 min-w-20 place-items-center rounded-2xl sm:right-4 sm:top-4">
          <div className={`flex flex-col items-center gap-1.5 ${enLlamada ? "text-accent" : "text-ink-3"}`}>
            {enLlamada ? (
              <Mic width={18} height={18} className={escucha.parcial ? "animate-pulse" : ""} />
            ) : (
              <CameraOff width={18} height={18} />
            )}
            <span className="text-[11px]">Vos</span>
          </div>
        </div>

        {/* nombre */}
        <div className="glass absolute left-3 top-3 flex items-center gap-2 rounded-full py-1.5 pl-2.5 pr-3.5 sm:left-4 sm:top-4">
          <span
            className={`size-2 rounded-full ${enLlamada ? "bg-live shadow-[0_0_10px_var(--live)]" : "bg-ink-3"} ${voz.hablando ? "animate-pulse" : ""}`}
          />
          <span className="text-[13px] font-medium">{nombre}</span>
        </div>

        {/* informe del docente */}
        {enLlamada && ultimoDocente && cerrado !== ultimoIdx && (
          <div
            key={ultimoIdx}
            className="glass enter absolute inset-x-3 top-16 max-h-[45%] overflow-y-auto rounded-2xl p-4 sm:inset-x-auto sm:left-4 sm:top-16 sm:max-w-sm"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-accent">
                <Stethoscope width={14} height={14} /> Docente
              </span>
              <button
                aria-label="Cerrar informe"
                onClick={() => setCerrado(ultimoIdx)}
                className="press text-ink-3 hover:text-ink"
              >
                <Close width={16} height={16} />
              </button>
            </div>
            <p className="whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed">{ultimoDocente.text}</p>
          </div>
        )}

        {/* llamada entrante */}
        {!enLlamada && (
          <div className="absolute inset-x-3 bottom-6 flex flex-col items-center gap-1 text-center">
            <p className="text-[19px] font-medium">{nombre}</p>
            <p className="text-[13px] text-ink-2">
              {!escucha.soportado
                ? "Tu navegador no permite llamadas de voz: usá Chrome, Edge o Safari, o el modo Chat"
                : listo
                  ? "Llamada entrante…"
                  : "Conectando…"}
            </p>
          </div>
        )}

        {/* compañera de estudio */}
        {enLlamada && (
          <div className="absolute bottom-20 left-2 z-10 flex flex-col items-start gap-2 sm:bottom-24 sm:left-4">
            {((conTutor && pregunto && tutor.pensando) || (ultimaVisible && ultimaTutor)) && (
              <p
                key={tutor.charla.length}
                className="vidrio-oscuro enter max-w-[min(22rem,calc(100cqw-1.5rem))] origin-bottom-left rounded-2xl rounded-bl-md px-3.5 py-2.5 text-[14.5px] leading-snug text-ink"
              >
                {tutor.pensando || !ultimaTutor ? (
                  <span className="text-ink-2">Buscando en los apuntes…</span>
                ) : (
                  <TextoEscrito texto={ultimaTutor} animar />
                )}
              </p>
            )}
            <div className="flex items-end gap-2">
              <button
              type="button"
              onClick={tocarMascota}
              aria-pressed={conTutor}
              aria-label={conTutor ? "Volver con el paciente" : `Hablarle a ${nombreTutor}, tu compañera de estudio`}
              title={conTutor ? "Volver con el paciente" : `¿Dudas? Hablale a ${nombreTutor}`}
              className={`press rounded-2xl p-1 transition-colors ${conTutor ? "bg-accent/15 ring-1 ring-accent/50" : ""}`}
            >
              <Mascota
                id={tutor.mascotaId}
                animacion={
                  tutor.pensando
                    ? "revisando"
                    : conTutor && vozDe === "tutor" && voz.hablando
                      ? "saludo"
                      : conTutor
                        ? "esperando"
                        : "reposo"
                }
                alto={100}
              />
            </button>
              {conTutor && !pregunto && (
                <p className="vidrio-oscuro enter mb-3 rounded-2xl rounded-bl-md px-3 py-2 text-[13px] text-ink-2">
                  Te escucho
                </p>
              )}
            </div>
          </div>
        )}

        {/* subtítulos */}
        {enLlamada && (
          <div className="absolute inset-x-3 bottom-4 flex justify-center sm:bottom-6">
            {escucha.parcial ? (
              <p className="max-w-2xl rounded-2xl bg-black/55 px-4 py-2.5 text-center text-[15px] leading-snug text-ink-2 backdrop-blur-md sm:text-[17px]">
                {escucha.parcial}
              </p>
            ) : conTutor ? null : pensando ? (
              <span className="rounded-full bg-black/55 px-4 py-2 text-[13px] text-ink-2 backdrop-blur-md">
                {nombre.split(" ")[0]} está pensando…
              </span>
            ) : ultimoPaciente ? (
              <p
                key={idxPaciente}
                aria-live="polite"
                className={
                  SUBTITULOS_PACIENTE
                    ? "enter max-w-2xl rounded-2xl bg-black/55 px-4 py-2.5 text-center text-[15px] leading-snug text-ink backdrop-blur-md sm:text-[17px]"
                    : "sr-only"
                }
              >
                {ultimoPaciente.text}
              </p>
            ) : (
              <span className="rounded-full bg-black/55 px-4 py-2 text-[13px] text-ink-2 backdrop-blur-md">
                Conectado · saludá para empezar
              </span>
            )}
          </div>
        )}
      </div>

      {/* controles: solo contestar y cortar, como una llamada */}
      <div className="flex items-start justify-center gap-14 pb-1 pt-1">
        <BotonLlamada etiqueta="Cortar" onClick={cortar} className="bg-danger hover:brightness-110">
          <PhoneDown width={26} height={26} />
        </BotonLlamada>
        {!enLlamada && (
          <BotonLlamada
            etiqueta="Contestar"
            onClick={contestar}
            disabled={!listo || !escucha.soportado}
            className="bg-live hover:brightness-110"
          >
            <Phone width={24} height={24} />
          </BotonLlamada>
        )}
      </div>
    </div>
  );
}

function BotonLlamada({
  etiqueta,
  onClick,
  disabled,
  className,
  children,
}: {
  etiqueta: string;
  onClick: () => void;
  disabled?: boolean;
  className: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <button
        type="button"
        aria-label={etiqueta}
        onClick={onClick}
        disabled={disabled}
        className={`press grid size-16 place-items-center rounded-full text-white disabled:opacity-40 ${className}`}
      >
        {children}
      </button>
      <span className="text-[12px] text-ink-2">{etiqueta}</span>
    </div>
  );
}
