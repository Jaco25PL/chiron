import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { signInAs, TEST_USER } from "./session";

// The study companion: a pet in a corner of the consultation that answers study questions (the fake
// backend's canned answers: the real one is RAG over the course notes). The patient never sees it and
// the clock stops while it's open. The pet is picked in the settings and saved per user.

const caso = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "..", "cases", "mpna", "mpna-disnea-icc.json"), "utf-8"),
);
const nombre = caso.paciente.nombre.split(" ").slice(0, 2).join(" ");

test.skip(!!process.env.BASE_URL, "uses the deterministic fake backend");

const usuario = () => ({ ...TEST_USER, email: `tutor-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com` });

async function abrirChat(page: Page, nivel: "Principiante" | "Normal") {
  await page.goto("/");
  await page.getByRole("tab", { name: nivel }).click();
  await page.locator("article").filter({ hasText: nombre }).getByRole("link", { name: "Chat" }).click();
  await expect(page).toHaveURL(/\/consulta\//);
}

async function preguntarTutor(page: Page, texto: string) {
  const charla = page.getByRole("region", { name: /Charla con/ });
  await charla.getByLabel(/Pregunta para/).fill(texto);
  // the session is created on load: retry until the question goes out
  await expect(async () => {
    await charla.getByRole("button", { name: "Preguntar" }).click({ timeout: 500 });
    await expect(charla.getByLabel(/Pregunta para/)).toHaveValue("", { timeout: 500 });
  }).toPass();
}

test("beginner: the pet answers, the patient doesn't see it, and the clock stops while it's open", async ({
  page,
  context,
  baseURL,
}) => {
  await signInAs(context, baseURL!, { user: usuario() });
  await abrirChat(page, "Principiante");

  const reloj = page.getByTitle(/Tiempo de la estación|Reloj en pausa/);
  await expect(reloj).toHaveAttribute("title", "Tiempo de la estación");
  await page.getByRole("button", { name: /Preguntarle a Hámster/ }).click();
  await expect(reloj).toHaveAttribute("title", /Reloj en pausa/);

  await preguntarTutor(page, "¿Cómo era la anamnesis?");
  const charla = page.getByRole("region", { name: "Charla con Hámster" });
  await expect(charla.getByText(/arrancá por la ficha patronímica/)).toBeVisible();

  await charla.getByRole("button", { name: "Cerrar" }).click();
  await expect(charla).toBeHidden();
  await expect(reloj).toHaveAttribute("title", "Tiempo de la estación");
  // nothing of it reached the consultation
  await expect(page.getByText("¿Cómo era la anamnesis?")).toBeHidden();
});

test("normal: the pet gives hints, and the summary says how often it was asked", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!, { user: usuario() });
  await abrirChat(page, "Normal");

  await page.getByRole("button", { name: /Preguntarle a Hámster/ }).click();
  await preguntarTutor(page, "No me acuerdo de la anamnesis");
  await expect(page.getByText(/¿te acordás qué sigue\?/)).toBeVisible();
  await page.getByRole("button", { name: /Cerrar la charla/ }).click();

  await page.locator("#mensaje").fill("Hola, buenas tardes");
  await page.locator("#mensaje").press("Enter");
  await expect(page.getByText("Buenas, doctor.")).toBeVisible();
  await page.getByRole("button", { name: "Terminar" }).first().click();
  const resumen = page.getByRole("dialog");
  await expect(resumen.getByText("Consulta terminada")).toBeVisible();
  await expect(resumen).toContainText("Le consultaste a tu compañera de estudio una vez");
});

test("the pet picked in the settings is saved and shows up in the consultation", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!, { user: usuario() });
  await page.goto("/");
  await page.getByRole("button", { name: "Cuenta" }).click();
  const ajustes = page.getByRole("dialog", { name: "Ajustes" });
  await expect(ajustes.getByRole("radio", { name: "Hámster" })).toBeChecked(); // the default

  const guardado = page.waitForResponse((r) => r.url().endsWith("/api/preferencias") && r.request().method() === "POST");
  await ajustes.getByText("Boba", { exact: true }).click();
  const r = await guardado;
  expect(r.status()).toBe(200);
  expect((await r.json()).mascota).toBe("boba");

  // another browser: it comes from the account, not from this one
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByRole("button", { name: "Cuenta" }).click();
  await expect(page.getByRole("dialog", { name: "Ajustes" }).getByRole("radio", { name: "Boba" })).toBeChecked();
  await page.keyboard.press("Escape");

  await abrirChat(page, "Normal");
  await expect(page.getByRole("button", { name: /Preguntarle a Boba/ })).toBeVisible();
});
