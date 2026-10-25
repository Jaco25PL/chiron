"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Chat, Video } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { Segmented } from "@/components/Segmented";
import { UserMenu, type Usuario } from "@/components/UserMenu";
import { ALEATORIO, api, iniciales, sexoLabel, type Caso, type Nivel } from "@/lib/api";

type Materia = "mpna" | "pediatria";

const NIVEL_KEY = "chiron.nivel";

/** The level, remembered per browser. Storage may be unavailable (private mode, blocked): then "normal". */
function useNivel() {
  const [nivel, setNivel] = useState<Nivel>("normal");
  useEffect(() => {
    try {
      // localStorage needs window, so it is read after hydration
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (localStorage.getItem(NIVEL_KEY) === "principiante") setNivel("principiante");
    } catch {}
  }, []);
  const elegir = (n: Nivel) => {
    setNivel(n);
    try {
      localStorage.setItem(NIVEL_KEY, n);
    } catch {}
  };
  return [nivel, elegir] as const;
}

export function Home({ usuario }: { usuario: Usuario }) {
  const [materia, setMateria] = useState<Materia>("mpna");
  const [nivel, setNivel] = useNivel();
  const [casos, setCasos] = useState<Caso[] | null>(null);

  useEffect(() => {
    api.casos(materia).then(setCasos).catch((e: Error) => {
      setCasos([]);
      toast.error(e.message, { id: "casos" }); // id: no duplicate toast if the effect runs twice
    });
  }, [materia]);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-[max(20px,env(safe-area-inset-left))] pb-16 pt-[max(24px,env(safe-area-inset-top))] sm:gap-14">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">Chiron</span>
        </div>
        <UserMenu usuario={usuario} />
      </header>

      <section className="flex flex-col gap-5 pt-4 sm:pt-10">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">Evaluación clínica objetiva estructurada</p>
        <h1 className="max-w-3xl text-balance text-[2.6rem] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-6xl">
          Tu próximo paciente ya está en la sala de espera.
        </h1>
        <p className="max-w-xl text-pretty text-[17px] leading-relaxed text-ink-2">
          Hacé la anamnesis, examinalo y pedí estudios como en la estación real. Siete minutos, una grilla, y el paciente
          solo responde lo que le preguntás.
        </p>
      </section>

      <section className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Elegí un paciente</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              id="materia"
              value={materia}
              onChange={setMateria}
              options={[
                { value: "mpna", label: "MPNA" },
                { value: "pediatria", label: "Pediatría", disabled: true, hint: "Próximamente" },
              ]}
            />
            <Segmented
              id="nivel"
              value={nivel}
              onChange={setNivel}
              options={[
                { value: "principiante", label: "Principiante" },
                { value: "normal", label: "Normal" },
              ]}
            />
          </div>
        </div>
        <p className="-mt-2 text-pretty text-sm text-ink-3">
          {nivel === "principiante"
            ? "Principiante: durante la consulta ves la lista de lo que no te podés olvidar, y se tacha sola a medida que lo hacés."
            : "Normal: como en el examen, sin ayuda. El mismo paciente, sin la lista."}
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          {casos === null
            ? [0, 1, 2, 3].map((i) => <div key={i} className="glass h-[150px] animate-pulse rounded-3xl" />)
            : [
                <RandomCard key={ALEATORIO} index={0} nivel={nivel} />,
                ...casos.map((c, i) => <CaseCard key={c.id} caso={c} index={i + 1} nivel={nivel} />),
              ]}
        </div>
      </section>
    </main>
  );
}

/** A patient card shows what the student knows at the door: name and sex. */
function CaseCard({ caso, index, nivel }: { caso: Caso; index: number; nivel: Nivel }) {
  const p = caso.paciente;
  return (
    <Card index={index} href={caso.id} nivel={nivel}>
      <div className="grid size-11 shrink-0 place-items-center rounded-full bg-glass-strong font-mono text-sm text-accent">
        {iniciales(p.nombre)}
      </div>
      <div className="min-w-0">
        <h3 className="truncate text-[17px] font-semibold tracking-tight">{p.nombre.split(" ").slice(0, 2).join(" ")}</h3>
        <p className="truncate text-sm text-ink-2">{sexoLabel(p.sexo)}</p>
      </div>
    </Card>
  );
}

/** Closest to the real exam: you don't know who is waiting until you walk in. */
function RandomCard({ index, nivel }: { index: number; nivel: Nivel }) {
  return (
    <Card index={index} href={ALEATORIO} nivel={nivel} destacada>
      <div className="grid size-11 shrink-0 place-items-center rounded-full border border-dashed border-accent/60 font-mono text-lg text-accent">
        ?
      </div>
      <div className="min-w-0">
        <h3 className="truncate text-[17px] font-semibold tracking-tight">Paciente aleatorio</h3>
        <p className="truncate text-sm text-ink-2">Como en el ECOE: no sabés quién te toca</p>
      </div>
    </Card>
  );
}

function Card({
  index,
  href,
  nivel,
  destacada,
  children,
}: {
  index: number;
  href: string;
  nivel: Nivel;
  destacada?: boolean;
  children: React.ReactNode;
}) {
  return (
    <article
      className={`glass enter flex flex-col gap-5 rounded-3xl p-5 ${destacada ? "border-accent/30 bg-accent/[0.04]" : ""}`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-center gap-3">{children}</div>
      <div className="mt-auto grid grid-cols-2 gap-2">
        <Link
          href={`/consulta/${href}?modo=chat&nivel=${nivel}`}
          className="press flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-full border border-line-strong text-sm font-medium text-ink hover:bg-glass-strong"
        >
          <Chat width={17} height={17} /> Chat
        </Link>
        <Link
          href={`/consulta/${href}?modo=cara&nivel=${nivel}`}
          className="press flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-full bg-ink text-sm font-medium text-bg hover:bg-white"
        >
          <Video width={17} height={17} /> Cara a cara
        </Link>
      </div>
    </article>
  );
}
