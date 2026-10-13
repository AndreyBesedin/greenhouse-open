import { cpus, platform, totalmem } from "node:os";

import type { Browser, Page } from "@playwright/test";

// How a benchmark measures a scene from what the HUD reports, while the
// camera orbits: the stress scene's (`stress.bench.ts`) and the reference
// greenhouse's (`reference.bench.ts`).

// Let the scene settle before measuring; the first HUD sample after a load is
// not a full window of frames.
const WARM_UP_MS = 1_500;
// The HUD reports four times a second; this many reports are kept.
const REPORTS = 16;
const REPORT_INTERVAL_MS = 250;
// The orbit: a drag across the view, a few pixels per report.
const DRAG_START = { x: 640, y: 400 };
const DRAG_STEP_PX = 15;
const DRAG_MOVES_PER_REPORT = 5;
const GIB = 1_073_741_824;

/** What the HUD said of a scene while the camera orbited it. */
export interface Orbited {
  medianFramesPerSecond: number;
  medianFrameMs: number;
  worstFrameMs: number;
  drawCalls: number;
  triangles: number;
}

/** The machine, browser and graphics a benchmark ran on. */
export interface RanOn {
  recorded: string;
  machine: { platform: string; cpu: string; cores: number; memoryGib: number };
  browser: string;
  renderer: string;
  viewport: string;
}

export function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2
    : (sorted[middle] ?? 0);
}

export function numbersIn(text: string | null): number[] {
  // Numbers as the HUD writes them, thousands separated: 4, 9,600,002 or 16.7.
  return (text ?? "").match(/\d[\d,]*(\.\d+)?/g)?.map((n) => Number(n.replaceAll(",", ""))) ?? [];
}

async function webglRenderer(page: Page): Promise<string> {
  return page.evaluate(() => {
    const gl = document.createElement("canvas").getContext("webgl2");
    const info = gl?.getExtension("WEBGL_debug_renderer_info");
    return gl && info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "unknown";
  });
}

/** What the benchmark runs on, read from the page open in `browser`. */
export async function ranOn(page: Page, browser: Browser): Promise<RanOn> {
  return {
    recorded: new Date().toISOString().slice(0, "YYYY-MM-DD".length),
    machine: {
      platform: `${platform()} ${process.arch}`,
      cpu: cpus()[0]?.model ?? "unknown",
      cores: cpus().length,
      memoryGib: Math.round(totalmem() / GIB),
    },
    browser: `Chromium ${browser.version()}`,
    renderer: await webglRenderer(page),
    viewport: "1280 x 720",
  };
}

/** Orbits the scene on show, and gathers what the HUD reports meanwhile. */
export async function orbit(page: Page): Promise<Orbited> {
  await page.waitForTimeout(WARM_UP_MS);
  const rates: number[] = [];
  const frameTimes: number[] = [];
  let worst = 0;
  await page.mouse.move(DRAG_START.x, DRAG_START.y);
  await page.mouse.down();
  for (let report = 0; report < REPORTS; report += 1) {
    const x = DRAG_START.x + (report % (REPORTS / 2)) * DRAG_STEP_PX;
    await page.mouse.move(x, DRAG_START.y, { steps: DRAG_MOVES_PER_REPORT });
    await page.waitForTimeout(REPORT_INTERVAL_MS);
    const [rate = 0] = numbersIn(await page.getByTestId("frame-rate").textContent());
    const [mean = 0, longest = 0] = numbersIn(await page.getByTestId("frame-time").textContent());
    rates.push(rate);
    frameTimes.push(mean);
    worst = Math.max(worst, longest);
  }
  await page.mouse.up();
  const [drawCalls = 0, triangles = 0] = numbersIn(
    await page.getByTestId("draw-calls").textContent(),
  );
  return {
    medianFramesPerSecond: Math.round(median(rates)),
    medianFrameMs: Number(median(frameTimes).toFixed(1)),
    worstFrameMs: worst,
    drawCalls,
    triangles,
  };
}
