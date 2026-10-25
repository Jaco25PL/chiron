import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// The main user journey, end to end: pick a case → interview → examine → order a study →
// switch to face to face → end → summary. Against the fake backend it is deterministic; the
// expected answers are read from the same case JSON the backend serves.

const CASE_ID = "mpna-disnea-icc";
const caso = JSON.parse(readFileSync(join(__dirname, "..", "..", "..", "cases", "mpna", `${CASE_ID}.json`), "utf-8"));
const fact = (id: string) => caso.anamnesis.find((h: { id: string }) => h.id === id);

test.skip(!!process.env.BASE_URL, "uses the deterministic fake backend; prod is covered by backend.spec");

test("a full consultation, from case selection to summary", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);

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

  // 4. same consultation in face-to-face mode: the last patient line becomes the caption
  await page.getByRole("tab", { name: "Cara a cara" }).click();
  await expect(page.getByLabel(/Retrato de/)).toBeVisible();
  await expect(page.getByText(inicio.respuesta)).toBeVisible();

  // 5. end it: the summary counts what the student obtained
  await page.getByLabel("Terminar consulta").click();
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

