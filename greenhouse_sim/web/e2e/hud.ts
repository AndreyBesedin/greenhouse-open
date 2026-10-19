import { expect, type Page } from "@playwright/test";

// The HUD samples the scene a few times a second, and counts its objects.
const SAMPLE_WAIT_MS = 1_000;
// Drawing in software on CI can take a while.
export const DRAWN_TIMEOUT_MS = 30_000;

/** The simulated day the HUD shows for a live scenario, or -1 before the first frame. */
export async function simulatedDay(page: Page): Promise<number> {
  const text = (await page.getByTestId("simulation-time").textContent()) ?? "";
  const match = /^day (\d+) · /.exec(text);
  return match?.[1] === undefined ? -1 : Number(match[1]);
}

/** How many objects the HUD last counted in the scene. */
export async function objectCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("object-count").textContent());
}

/** The scene's object count once it has stopped changing. */
export async function settledObjectCount(page: Page): Promise<number> {
  let last = Number.NaN;
  await expect
    .poll(
      async () => {
        const now = await objectCount(page);
        const settled = now === last;
        last = now;
        return settled;
      },
      { intervals: [SAMPLE_WAIT_MS], timeout: DRAWN_TIMEOUT_MS },
    )
    .toBe(true);
  return last;
}
