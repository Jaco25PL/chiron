import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// /revision: a medical student labels the patient's eval answers to calibrate the LLM judge.
// The fake backend serves two demo answers; only the emails in CHIRON_REVIEWERS may open it.
test.skip(!!process.env.BASE_URL, "uses the fake backend's demo answers");

const REVISORA = { name: "Revisora", email: "revisora@example.com", picture: null };

test("a reviewer labels the answers, and the labels are kept", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!, { user: REVISORA });
  await page.goto("/revision");
  await expect(page.getByText("0 de 2")).toBeVisible();
  await expect(page.getByText("¿Qué lo trae por acá?")).toBeVisible();
  await expect(page.getByText("solo el motivo de consulta")).toBeVisible();

  await page.getByRole("button", { name: "Todo bien" }).click(); // all five ✓, then the next one
  await expect(page.getByText("1 de 2")).toBeVisible();
  await expect(page.getByText("¿Usted qué cree que tiene?")).toBeVisible();

  await page.getByRole("button", { name: "No revela el diagnóstico: sí" }).click();
  await page.getByRole("button", { name: "No inventa: sí" }).click();
  const jerga = page.getByRole("button", { name: "Habla como un paciente: no" });
  await jerga.click();
  await expect(jerga).toHaveAttribute("aria-pressed", "true");
  await page.getByPlaceholder("¿Algo para comentar?").fill("Suena un poco formal");
  await page.getByPlaceholder("¿Algo para comentar?").blur();
  await expect(page.getByText("¡Listo, revisaste todas!")).toBeVisible();

  await page.reload(); // saved on the server
  await expect(page.getByText("2 de 2")).toBeVisible();
  await page.getByRole("button", { name: "Siguiente" }).click(); // all done: it reopens on the first one
  await expect(page.getByRole("button", { name: "Habla como un paciente: no" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByPlaceholder("¿Algo para comentar?")).toHaveValue("Suena un poco formal");
});

test("students can't open the review: it shows the hidden diagnoses", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!);
  await page.goto("/revision");
  await expect(page.getByText("solo para quienes revisan el corrector")).toBeVisible();
  await expect(page.getByText("¿Qué lo trae por acá?")).toHaveCount(0);
});
