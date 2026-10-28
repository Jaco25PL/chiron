import { readFileSync } from "node:fs";
import { join } from "node:path";
import { nombreCorto } from "../../lib/api";
import { expect, test, type Page } from "@playwright/test";
import { signInAs } from "./session";

// Difficulty levels: same patient; "Principiante" adds the grilla checklist, ticked as the student
// covers each item. Against the fake backend (keyword replies from the real case JSON).

const CASE_ID = "mpna-disnea-icc";
const caso = JSON.parse(readFileSync(join(__dirname, "..", "..", "..", "cases", "mpna", `${CASE_ID}.json`), "utf-8"));
const inicio = caso.anamnesis.find((h: { id: string }) => h.id === "inicio");
const itemInicio = (inicio.grilla_items[0] as string).split("::")[1];

test.skip(!!process.env.BASE_URL, "uses the deterministic fake backend");
test.beforeEach(async ({ context, baseURL }) => signInAs(context, baseURL!));

async function enviar(page: Page, text: string) {
  // Enter is ignored until the session exists (it's created on load): retry until the box empties
  await page.locator("#mensaje").fill(text);
  await expect(async () => {
    await page.locator("#mensaje").press("Enter");
    await expect(page.locator("#mensaje")).toHaveValue("", { timeout: 500 });
  }).toPass();
}

test("beginner: the level is remembered and the checklist ticks itself as the student asks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Normal" })).toHaveAttribute("aria-selected", "true"); // default
  await page.getByRole("tab", { name: "Principiante" }).click();
  await page.reload();
  await expect(page.getByRole("tab", { name: "Principiante" })).toHaveAttribute("aria-selected", "true");

  const nombre = nombreCorto(caso.paciente.nombre);
  await page.locator("article").filter({ hasText: nombre }).getByRole("link", { name: "Atender" }).click();
  await expect(page).toHaveURL(/\?modo=cara&nivel=principiante/);
  await page.getByRole("tab", { name: "Chat" }).click();
  await expect(page.locator("header")).toContainText("Principiante");

  // desktop: a side panel, grouped by what to do, nothing done yet
  const panel = page.getByRole("complementary", { name: "Checklist" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("region", { name: "Preguntá" })).toBeVisible();
  await expect(panel.getByRole("region", { name: "Examiná" })).toBeVisible();
  await expect(panel).toContainText("los evalúa el docente al final");
  const item = panel.locator("li", { hasText: itemInicio });
  await expect(item).toHaveAttribute("data-hecho", "false");

  // asking about it crosses it out
  await enviar(page, inicio.preguntas_ejemplo[0]);
  await expect(page.getByText(inicio.respuesta)).toBeVisible();
  await expect(item).toHaveAttribute("data-hecho", "true");
  await expect(page.getByRole("button", { name: /^Checklist: 1 de/ })).toBeVisible();

  // it can be hidden and brought back from the header
  await panel.getByRole("button", { name: "Ocultar checklist" }).click();
  await expect(panel).toHaveCount(0);
  await page.getByRole("button", { name: /^Checklist/ }).click();
  await expect(page.getByRole("complementary", { name: "Checklist" })).toBeVisible();

  // the checklist never names the hidden diagnosis
  await expect(page.locator("body")).not.toContainText(caso.diagnostico.principal);
});

test("beginner on a phone: a pill opens the checklist as a bottom sheet, also in the call", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/consulta/aleatorio?modo=cara&nivel=principiante");
  await expect(page.getByRole("complementary", { name: "Checklist" })).toBeHidden();
  const pill = page.getByRole("button", { name: /^Checklist: 0 de \d+ hechos$/ });
  await pill.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("region", { name: "Preguntá" })).toBeVisible();
  await expect(sheet).toContainText("Saludar, presentarte, explicar y pedir permiso también cuentan");
  // the call keeps its two buttons
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("button", { name: "Contestar" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cortar" })).toBeVisible();
});

test("normal: no checklist anywhere, and the browser never receives it", async ({ page }) => {
  const respuestas: Promise<string>[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/sessions")) respuestas.push(r.text().catch(() => ""));
  });
  await page.goto("/consulta/aleatorio?modo=chat&nivel=normal");
  await expect(page.locator("header")).toContainText("Normal");
  await enviar(page, "Hola, buenas tardes");
  await expect(page.getByText("Buenas, doctor.")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Checklist/ })).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Checklist" })).toHaveCount(0);
  const cuerpos = await Promise.all(respuestas);
  expect(cuerpos.length).toBeGreaterThanOrEqual(2); // the session and the message
  for (const r of cuerpos) expect(r).not.toContain("checklist");
});
