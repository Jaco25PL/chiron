import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// The history side menu: every finished consultation with its score and what to remember next time.
// Each test uses its own user: the fake backend keeps everyone's consultations in memory.

test("history starts empty and lists each finished consultation with its score", async ({ page, context, baseURL }) => {
  test.skip(!!process.env.BASE_URL, "creates and grades consultations on the fake backend");
  await signInAs(context, baseURL!, { user: { name: "Historia", email: "historia@example.com", picture: null } });
  await page.goto("/");
  await page.getByRole("button", { name: "Historial" }).click();
  await expect(page.getByText("Todavía no terminaste ninguna consulta")).toBeVisible();
  await page.keyboard.press("Escape");

  // a consultation, ended: the docente grades it and it shows up the next time the menu opens
  const s = await page.request.post("/api/sessions", { data: { case_id: "mpna-disnea-icc", mode: "cara" } });
  const { session_id, case: caso } = await s.json();
  await page.request.post(`/api/sessions/${session_id}/messages`, { data: { text: "Hola, buenas tardes" } });
  const fin = await (await page.request.post(`/api/sessions/${session_id}/finish`)).json();

  await page.getByRole("button", { name: "Historial" }).click();
  const panel = page.getByRole("dialog", { name: "Tu historial" });
  await expect(panel.getByText("Promedio de las últimas 1")).toBeVisible();
  const nombre = caso.paciente.nombre.split(" ").slice(0, 2).join(" ");
  await expect(panel.getByRole("listitem").filter({ hasText: nombre })).toContainText(`${fin.feedback.score}/100`);
  await expect(panel).toContainText("Cara a cara");
  await expect(panel.getByRole("button", { name: new RegExp(`: ${fin.feedback.score} de 100`) })).toBeVisible();
  await expect(panel).not.toContainText("mpna-"); // never an internal case id
});
