import { writeFile } from "node:fs/promises";
import type { Page, TestInfo } from "@playwright/test";

// What a recorded walk-through's steps share: a caption over the page, a
// moment lingered on it, and the mark of its opening shot. As a browser test
// a walk-through lingers on nothing; recorded (playwright.demo.config.ts), it
// lingers for DEMO_PAUSE_MS.

const PAUSE_MS = Number(process.env.DEMO_PAUSE_MS ?? 0);
const STARTED = Date.now();
// The file `uv run record-demo` cuts the video from
// (tools/greenhouse_dev/demo_video.py).
const OPENING_MARK = "opening.json";

/** Shows a step's caption over the page. In the top layer, and shown anew each
 * time: a modal dialog opened since would cover it otherwise. */
export async function caption(page: Page, text: string): Promise<void> {
  console.log(`STEP ${((Date.now() - STARTED) / 1000).toFixed(0)} s: ${text}`);
  await page.evaluate((said) => {
    const shown =
      document.getElementById("demo-caption") ??
      document.body.appendChild(
        Object.assign(document.createElement("div"), { id: "demo-caption", popover: "manual" }),
      );
    shown.textContent = said;
    shown.setAttribute(
      "style",
      "position:fixed;inset:auto auto 16px 50%;margin:0;border:0;transform:translateX(-50%);" +
        "padding:8px 14px;border-radius:6px;background:rgb(0 0 0 / 75%);color:#fff;" +
        "font:16px system-ui;pointer-events:none",
    );
    if (shown.matches(":popover-open")) {
      shown.hidePopover();
    }
    shown.showPopover();
  }, text);
}

/** Stays on what is shown, for `share` of DEMO_PAUSE_MS. */
export async function linger(page: Page, share = 1): Promise<void> {
  if (PAUSE_MS > 0) {
    await page.waitForTimeout(PAUSE_MS * share);
  }
}

/** Shows a step's caption, and lingers on it. */
export async function say(page: Page, text: string, share = 1): Promise<void> {
  await caption(page, text);
  await linger(page, share);
}

/** Notes that the opening shot is ready, in seconds into the video, which
 * started at `recordingFrom` (Date.now()): the video is cut from there, and its
 * first frame is the README's preview. */
export async function markOpening(testInfo: TestInfo, recordingFrom: number): Promise<void> {
  await writeFile(
    testInfo.outputPath(OPENING_MARK),
    JSON.stringify({ opening_s: (Date.now() - recordingFrom) / 1000 }),
  );
}
