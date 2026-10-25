import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// Latency of a face-to-face turn, measured in the browser along the real path (browser → Next proxy →
// chiron-api → Gemini). Not part of the suite: it spends Gemini quota.
//
//   LATENCIA=1 BASE_URL=https://chiron-nu-two.vercel.app npx playwright test latencia [--workers 1]
//   LATENCIA_OUT=file.json writes every turn's numbers.
test.skip(!process.env.LATENCIA, "spends Gemini quota: run it on purpose with LATENCIA=1");
test.setTimeout(300_000);

const CONSULTAS = [
  {
    caso: "mpna-dolor-toracico-angina",
    preguntas: ["Hola, buenas tardes", "¿Qué lo trae por acá?", "¿Desde cuándo le pasa?", "¿Fuma?"],
  },
  {
    caso: "mpna-itu-pna-diabetica",
    preguntas: ["Buenas tardes, señora", "¿Qué la trae?", "¿Cómo es el dolor?", "¿Tiene fiebre?"],
  },
];

test("face-to-face turn latency", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);
  await page.goto("/login"); // any page of the app, to run fetch from its origin
  await page.request.get("/api/cases"); // wake the functions up: cold starts are measured apart

  const turnos: { caso: string; texto: string; texto_ms: number; suena_ms: number }[] = [];
  for (const { caso, preguntas } of CONSULTAS) {
    const s = await page.request.post("/api/sessions", { data: { case_id: caso, mode: "cara" } });
    expect(s.status()).toBe(200);
    const { session_id } = await s.json();
    for (const texto of preguntas) {
      const t = await page.evaluate(
        async ({ id, texto }) => {
          const ms = (t0: number) => Math.round(performance.now() - t0);
          const t0 = performance.now();
          // stream=1: text and voice in one streamed response (NDJSON). Otherwise the two requests.
          const res = await fetch(`/api/sessions/${id}/messages?voz=1`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ text: texto }),
          });
          if (res.headers.get("content-type")?.includes("ndjson")) {
            const reader = res.body!.getReader();
            const dec = new TextDecoder();
            let buf = "";
            let texto_ms = 0;
            let audio_ms = 0;
            let timings = {};
            for (;;) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += dec.decode(value, { stream: true });
              let i;
              while ((i = buf.indexOf("\n")) >= 0) {
                const linea = JSON.parse(buf.slice(0, i));
                buf = buf.slice(i + 1);
                if (linea.tipo === "respuesta") {
                  texto_ms = ms(t0);
                  timings = linea.debug.timings;
                } else if (linea.tipo === "audio" && !audio_ms) audio_ms = ms(t0);
              }
            }
            return { modo: "stream", texto_ms, suena_ms: audio_ms, fin_ms: ms(t0), timings };
          }
          const r = await res.json();
          const texto_ms = ms(t0);
          const v = await fetch(`/api/sessions/${id}/voz`, { method: "POST" });
          const reader = v.body!.getReader();
          let primer = 0;
          for (;;) {
            const { done } = await reader.read();
            if (done) break;
            primer = primer || ms(t0);
          }
          // a WAV can only be decoded once complete: the patient starts speaking when it has all arrived
          return {
            modo: "dos pedidos",
            texto_ms,
            primer_byte_voz_ms: primer,
            suena_ms: ms(t0),
            fin_ms: ms(t0),
            timings: r.debug.timings,
          };
        },
        { id: session_id, texto },
      );
      turnos.push({ caso, texto, ...t });
      console.log(JSON.stringify({ texto, ...t }));
    }
  }
  const mediana = (k: "texto_ms" | "suena_ms") => {
    const v = turnos.map((t) => t[k]).sort((a, b) => a - b);
    return v[Math.floor(v.length / 2)];
  };
  console.log(`median: text ${mediana("texto_ms")} ms, patient starts speaking ${mediana("suena_ms")} ms`);
  if (process.env.LATENCIA_OUT) writeFileSync(process.env.LATENCIA_OUT, JSON.stringify(turnos, null, 1));
});
