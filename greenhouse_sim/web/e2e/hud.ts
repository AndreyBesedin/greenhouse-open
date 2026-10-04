import type { Page } from "@playwright/test";

/** The simulated day the HUD shows for a live scenario, or -1 before the first frame. */
export async function simulatedDay(page: Page): Promise<number> {
  const text = (await page.getByTestId("simulation-time").textContent()) ?? "";
  const match = /^day (\d+) · /.exec(text);
  return match?.[1] === undefined ? -1 : Number(match[1]);
}
