import { expect, type Page, test } from "@playwright/test";

import { IDLE_AFTER_MS } from "../src/frameMeter.ts";
import { mainView } from "./view.ts";

// Long enough to see a frame drawn at each of the HUD's idle reports, were
// one to draw again: twice the wait before the view counts as still.
const STILL_MS = 2 * IDLE_AFTER_MS + 500;
const HELD_MS = 1000;
// Frames a held drag draws in a second, at the least, on CI's software
// renderer; without the pointer moving, a view drawn on demand would draw none.
const HELD_FRAMES = 3;

/** Counts the frames the page draws, as the renderer's clears: one a frame. */
async function countFrames(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const counted = window as unknown as { frames: number };
    counted.frames = 0;
    for (const context of [WebGL2RenderingContext, WebGLRenderingContext]) {
      const clear = context.prototype.clear;
      context.prototype.clear = function (this: WebGLRenderingContext, mask: number) {
        counted.frames += 1;
        clear.call(this, mask);
      };
    }
  });
}

/** The frames drawn over `ms` milliseconds from now. */
async function framesOver(page: Page, ms: number): Promise<number> {
  const drawn = () => page.evaluate(() => (window as unknown as { frames: number }).frames);
  const before = await drawn();
  await page.waitForTimeout(ms);
  return (await drawn()) - before;
}

test("the view draws nothing while it stands still, and every frame while a drag holds it", async ({
  page,
}) => {
  await countFrames(page);
  await page.goto("/?scene=example");
  const frameRate = page.getByTestId("frame-rate");
  await expect(page.getByTestId("scene-status")).toContainText("128 entities");
  await expect(frameRate).toHaveText("idle");

  // Still, it draws nothing, nor does the HUD's report that it is still
  // (decision 0053).
  expect(await framesOver(page, STILL_MS)).toBe(0);

  // Held in a drag, it draws on though the pointer rests, at the renderer's
  // own rate.
  const box = await mainView(page).boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  const centre = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.move(centre.x, centre.y);
  await page.mouse.down();
  await page.mouse.move(centre.x + 30, centre.y, { steps: 3 });
  expect(await framesOver(page, HELD_MS)).toBeGreaterThanOrEqual(HELD_FRAMES);
  await expect(frameRate).toHaveText(/^\d+ fps$/);

  // Let go, it stands still again.
  await page.mouse.up();
  await expect(frameRate).toHaveText("idle");
  expect(await framesOver(page, STILL_MS)).toBe(0);
});
