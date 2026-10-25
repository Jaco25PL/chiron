import type { BrowserContext, Page } from "@playwright/test";

/** Replaces the browser's speech recognition with a fake that "hears" the phrases queued with decir().
 *  Headless Chromium can't listen, and real recognition would make the test depend on Google. */
export async function microfonoFalso(context: BrowserContext) {
  await context.addInitScript(() => {
    const w = window as unknown as { __dichos: string[]; SpeechRecognition: unknown; webkitSpeechRecognition: unknown };
    w.__dichos = [];
    class ReconocimientoFalso {
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      lang = "";
      interimResults = false;
      continuous = false;
      start() {
        const t = w.__dichos.shift();
        setTimeout(() => {
          if (t) this.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: t }], { isFinal: true })] });
          this.onend?.();
        }, t ? 50 : 300); // silence: ends without a result, like the real one after a while
      }
      stop() {}
      abort() {
        this.onend = null;
      }
    }
    w.SpeechRecognition = ReconocimientoFalso;
    w.webkitSpeechRecognition = ReconocimientoFalso;
  });
}

/** The student says a phrase during the call. */
export const decir = (page: Page, frase: string) =>
  page.evaluate((f) => (window as unknown as { __dichos: string[] }).__dichos.push(f), frase);
