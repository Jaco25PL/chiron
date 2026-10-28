import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { signInAs } from "./session";
import { decir, microfonoFalso } from "./voz";

// The main user journey, end to end: pick a case → interview → examine → order a study →
// switch to a face-to-face call → hang up → summary. Against the fake backend it is deterministic; the
// expected answers are read from the same case JSON the backend serves.

const CASE_ID = "mpna-disnea-icc";
const caso = JSON.parse(readFileSync(join(__dirname, "..", "..", "..", "cases", "mpna", `${CASE_ID}.json`), "utf-8"));
const fact = (id: string) => caso.anamnesis.find((h: { id: string }) => h.id === id);

test.skip(!!process.env.BASE_URL, "uses the deterministic fake backend; prod is covered by backend.spec");

test("a full consultation, from case selection to summary", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);
  await microfonoFalso(context);

  // 1. pick the patient: the card only says who they are, never what they have
  await page.goto("/");
  const nombre = caso.paciente.nombre.split(" ").slice(0, 2).join(" ");
  const card = page.locator("article").filter({ hasText: nombre });
  await expect(card).not.toContainText(caso.titulo);
  await expect(card).not.toContainText(String(caso.paciente.edad));
  await card.getByRole("link", { name: "Atender" }).click(); // face to face by default
  await expect(page).toHaveURL(/\/consulta\/[0-9a-f]{10}\?modo=cara/); // opaque id, not "mpna-disnea-icc"
  await page.getByRole("tab", { name: "Chat" }).click();

  // Enter is ignored until the session exists (it's created on load): retry until the box empties
  const send = async (text: string) => {
    await page.locator("#mensaje").fill(text);
    await expect(async () => {
      await page.locator("#mensaje").press("Enter");
      await expect(page.locator("#mensaje")).toHaveValue("", { timeout: 500 });
    }).toPass();
  };

  // 2. greet and interview: the patient answers only what is asked
  await send("Hola, buenas tardes, soy estudiante de medicina");
  await expect(page.getByText("Buenas, doctor.")).toBeVisible();
  const inicio = fact("inicio");
  await send(inicio.preguntas_ejemplo[0]);
  await expect(page.getByText(inicio.respuesta)).toBeVisible();

  // 3. physical exam and a study: the teacher reports the case's findings
  await send("Le tomo la presión arterial");
  await expect(page.getByText(`PA: ${caso.signos_vitales.pa}`)).toBeVisible();
  const ecg = caso.paraclinica.find((e: { estudio: string }) => /electrocardiograma/i.test(e.estudio));
  await send("Solicito un electrocardiograma");
  await expect(page.getByText(`${ecg.estudio}:`, { exact: false })).toBeVisible();

  // 4. same consultation as a call: answer, and the last patient line becomes the caption
  await page.getByRole("tab", { name: "Cara a cara" }).click();
  await expect(page.getByLabel(/Retrato de/)).toBeVisible();
  await page.getByRole("button", { name: "Contestar" }).click();
  await expect(page.getByText(inicio.respuesta)).toBeVisible();

  // 5. hang up: the docente grades the consultation against the grilla (the fake backend's
  // coverage-based correction) and the summary counts what the student obtained
  await page.getByRole("button", { name: "Cortar" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByText("Consulta terminada")).toBeVisible();
  await expect(sheet.getByLabel(/Puntaje: \d+ de 100/)).toBeVisible();
  await expect(sheet.getByText("Lo que hiciste bien")).toBeVisible();
  await expect(sheet.getByText("A mejorar")).toBeVisible();
  await expect(sheet).toContainText(`/${caso.anamnesis.length}`);
  await expect(sheet).toContainText(ecg.estudio);

  // the full grilla is collapsed until asked for, each item with its rating
  const grilla = sheet.getByRole("button", { name: /Grilla completa/ });
  await expect(grilla).toHaveAttribute("aria-expanded", "false");
  await grilla.click();
  await expect(grilla).toHaveAttribute("aria-expanded", "true");
  await expect(sheet.getByText("No realizado").first()).toBeVisible();

  // the hidden diagnosis never reaches the student's screen, not even in the correction
  await expect(page.locator("body")).not.toContainText(caso.diagnostico.principal);
  for (const key of caso.diagnostico.grilla_items ?? []) {
    await expect(page.locator("body")).not.toContainText(key.split("::")[1]);
  }

  // and the consultation is now in the student's history, with the public view of the patient only
  // (other tests may finish consultations in parallel with the same user, so look for this one)
  const historial: { paciente: object; score: number }[] = await (await page.request.get("/api/historial")).json();
  expect(historial.map((h) => h.paciente)).toContainEqual({ nombre: caso.paciente.nombre, sexo: caso.paciente.sexo });
  expect(JSON.stringify(historial)).not.toContain(CASE_ID);
});

test("random patient: the server picks the case and the student only learns name and sex", async ({
  page,
  context,
  baseURL,
}) => {
  await signInAs(context, baseURL!);
  await page.goto("/");
  const card = page.locator("article").filter({ hasText: "Paciente aleatorio" });
  await card.getByRole("link", { name: "Atender" }).click();
  await expect(page).toHaveURL(/\/consulta\/aleatorio\?modo=cara/);
  const header = page.locator("header");
  await expect(header).toContainText(/Paciente (masculino|femenina)/);
  await expect(page.getByLabel(/Retrato de/)).toBeVisible();
  // nothing beyond name and sex: no title, age, rubric or diagnosis anywhere on screen
  const body = await page.locator("body").innerText();
  for (const leak of ["Disnea de esfuerzo", "Dolor en el pecho", "Ardor al orinar", "grillas", "años"]) {
    expect(body).not.toContain(leak);
  }
});

test("face to face is a call: answer, talk hands-free, the patient speaks, hang up", async ({
  page,
  context,
  baseURL,
}) => {
  await signInAs(context, baseURL!);
  await microfonoFalso(context);
  // every phrase goes as one streamed request that brings the reply and then the voice
  const llamadas: string[] = [];
  page.on(
    "response",
    (r) => r.url().includes("/messages?voz=1") && llamadas.push(`${r.status()} ${r.headers()["content-type"]}`),
  );
  await page.goto("/consulta/aleatorio?modo=cara");

  // like a phone call: two buttons, no text box and no shortcut chips
  await expect(page.getByRole("button", { name: "Contestar" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Cortar" })).toBeVisible();
  await expect(page.locator("#mensaje")).toHaveCount(0);
  await expect(page.getByText("Le tomo los signos vitales")).toHaveCount(0);

  await page.getByRole("button", { name: "Contestar" }).click();
  await expect(page.getByRole("button", { name: "Contestar" })).toHaveCount(0);
  await expect(page.getByText("Conectado · saludá para empezar")).toBeVisible();

  // a phrase is sent when the student pauses; the reply is spoken (the fake backend streams silence)
  await decir(page, "Hola, buenas tardes");
  await expect(page.getByText("Buenas, doctor.")).toBeVisible();
  await expect.poll(() => llamadas).toEqual(["200 application/x-ndjson"]);
  await expect(page.getByText("No se pudo reproducir")).toHaveCount(0);

  // the exam is asked for out loud too; the teacher answers in writing (the backend sends no audio for it)
  await decir(page, "Le tomo la presión arterial");
  await expect(page.getByText("Docente")).toBeVisible();
  await expect(page.getByText("No se pudo reproducir")).toHaveCount(0);

  await page.getByRole("button", { name: "Cortar" }).click();
  await expect(page.getByRole("dialog").getByText("Consulta terminada")).toBeVisible();
});
