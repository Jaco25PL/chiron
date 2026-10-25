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
  await card.getByRole("link", { name: "Chat" }).click();
  await expect(page).toHaveURL(/\/consulta\/[0-9a-f]{10}\?/); // opaque id, not "mpna-disnea-icc"

  const send = async (text: string) => {
    await page.locator("#mensaje").fill(text);
    await page.keyboard.press("Enter");
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

  // 5. hang up: the summary counts what the student obtained
  await page.getByRole("button", { name: "Cortar" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByText("Consulta terminada")).toBeVisible();
  await expect(sheet).toContainText(`/${caso.anamnesis.length}`);
  await expect(sheet).toContainText(ecg.estudio);

  // the hidden diagnosis never reaches the student's screen
  await expect(page.locator("body")).not.toContainText(caso.diagnostico.principal);
});

test("random patient: the server picks the case and the student only learns name and sex", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);
  await page.goto("/");
  const card = page.locator("article").filter({ hasText: "Paciente aleatorio" });
  await card.getByRole("link", { name: "Cara a cara" }).click();
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


test("face to face is a call: answer, talk hands-free, the patient speaks, hang up", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);
  await microfonoFalso(context);
  const voces: number[] = [];
  page.on("response", (r) => r.url().endsWith("/voz") && voces.push(r.status()));
  await page.goto("/consulta/aleatorio?modo=cara");

  // like a phone call: two buttons, no text box and no shortcut chips
  await expect(page.getByRole("button", { name: "Contestar" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Cortar" })).toBeVisible();
  await expect(page.locator("#mensaje")).toHaveCount(0);
  await expect(page.getByText("Le tomo los signos vitales")).toHaveCount(0);

  await page.getByRole("button", { name: "Contestar" }).click();
  await expect(page.getByRole("button", { name: "Contestar" })).toHaveCount(0);
  await expect(page.getByText("Conectado · saludá para empezar")).toBeVisible();

  // a phrase is sent when the student pauses; the reply is spoken (the fake backend returns a silent WAV)
  await decir(page, "Hola, buenas tardes");
  await expect(page.getByText("Buenas, doctor.")).toBeVisible();
  await expect.poll(() => voces).toEqual([200]);
  await expect(page.getByText("No se pudo reproducir")).toHaveCount(0);

  // the exam is asked for out loud too; the teacher answers in writing, the patient's voice isn't used
  await decir(page, "Le tomo la presión arterial");
  await expect(page.getByText("Docente")).toBeVisible();
  expect(voces).toEqual([200]);

  await page.getByRole("button", { name: "Cortar" }).click();
  await expect(page.getByRole("dialog").getByText("Consulta terminada")).toBeVisible();
});
