"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Chat, Video } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { Segmented } from "@/components/Segmented";
import { UserMenu, type Usuario } from "@/components/UserMenu";
import { api, DIFICULTAD, iniciales, type Caso } from "@/lib/api";

type Materia = "mpna" | "pediatria";

export function Home({ usuario }: { usuario: Usuario }) {
  const [materia, setMateria] = useState<Materia>("mpna");
  const [casos, setCasos] = useState<Caso[] | null>(null);

  useEffect(() => {
    api.casos(materia).then(setCasos).catch((e: Error) => {
      setCasos([]);
      toast.error(e.message);
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
          <h2 className="text-lg font-semibold tracking-tight">Elegí un caso</h2>
          <Segmented
            id="materia"
            value={materia}
            onChange={setMateria}
            options={[
              { value: "mpna", label: "MPNA" },
              { value: "pediatria", label: "Pediatría", disabled: true, hint: "Próximamente" },
            ]}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {casos === null
            ? [0, 1, 2].map((i) => <div key={i} className="glass h-[214px] animate-pulse rounded-3xl" />)
            : casos.map((c, i) => <CaseCard key={c.id} caso={c} index={i} />)}
        </div>
      </section>
    </main>
  );
}

function CaseCard({ caso, index }: { caso: Caso; index: number }) {
  const p = caso.paciente;
  return (
    <article
      className="glass enter group flex flex-col gap-5 rounded-3xl p-5"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-center justify-between">
        <span className="rounded-full border border-line px-2.5 py-1 text-[11px] font-medium text-ink-2">
          {DIFICULTAD[caso.dificultad]}
        </span>
        <span className="font-mono text-[11px] text-ink-3">{caso.grillas.length} grillas</span>
      </div>

      <div className="flex items-center gap-3">
        <div className="grid size-11 shrink-0 place-items-center rounded-full bg-glass-strong font-mono text-sm text-accent">
          {iniciales(p.nombre)}
        </div>
        <div className="min-w-0">
          <h3 className="truncate text-[17px] font-semibold tracking-tight">{caso.titulo}</h3>
          <p className="truncate text-sm text-ink-2">
            {p.nombre.split(" ").slice(0, 2).join(" ")}, {p.edad} años
          </p>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-2 gap-2">
        <Link
          href={`/consulta/${caso.id}?modo=chat`}
          className="press flex h-10 items-center justify-center gap-2 rounded-full border border-line-strong text-sm font-medium text-ink hover:bg-glass-strong"
        >
          <Chat width={17} height={17} /> Chat
        </Link>
        <Link
          href={`/consulta/${caso.id}?modo=cara`}
          className="press flex h-10 items-center justify-center gap-2 rounded-full bg-ink text-sm font-medium text-bg hover:bg-white"
        >
          <Video width={17} height={17} /> Cara a cara
        </Link>
      </div>
    </article>
  );
}
