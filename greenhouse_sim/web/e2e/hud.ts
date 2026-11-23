import { expect, type Page } from "@playwright/test";

import { IDLE_AFTER_MS } from "../src/frameMeter.ts";

// The HUD counts the scene's objects at a frame at most every
// SAMPLE_INTERVAL_MS. A frame drawn sooner after the last count is counted
// only once the view has stood still for IDLE_AFTER_MS, so the count can
// trail the scene by that long: two counts that agree IDLE_AFTER_MS apart
// may both come before the frame that changed it. Twice as far apart, they
// leave that frame a second to be drawn.
const SAMPLE_WAIT_MS = 2 * IDLE_AFTER_MS;
// Drawing in software on CI can take a while.
export const DRAWN_TIMEOUT_MS = 30_000;

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
