import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { cpus, platform, totalmem } from "node:os";

import { expect, type Page, test } from "@playwright/test";

/**
 * Measures the stress scene at several sizes while the camera orbits, from
 * what the HUD reports, and compares the result with the recorded baseline.
 *
 *     npm run bench                  # measure and compare
 *     RECORD_BENCHMARK=1 npm run bench   # measure and record as the baseline
 */

const SIZES = [1_000, 10_000, 50_000, 100_000];
const BASELINE = new URL("../../benchmarks/stress.json", import.meta.url);
const LATEST = new URL("../../test-results/bench/stress.json", import.meta.url);
// Let the scene settle before measuring; the first HUD sample after a load is
// not a full window of frames.
const WARM_UP_MS = 1_500;
// The HUD reports four times a second; this many reports are kept per size.
const REPORTS = 16;
const REPORT_INTERVAL_MS = 250;
// The orbit: a drag across the view, a few pixels per report.
const DRAG_START = { x: 640, y: 400 };
const DRAG_STEP_PX = 15;
const DRAG_MOVES_PER_REPORT = 5;
const GIB = 1_073_741_824;

interface Measurement {
  plants: number;
  medianFramesPerSecond: number;
  medianFrameMs: number;
  worstFrameMs: number;
  drawCalls: number;
  triangles: number;
}

interface Benchmark {
  recorded: string;
  machine: { platform: string; cpu: string; cores: number; memoryGib: number };
  browser: string;
  renderer: string;
  viewport: string;
  measurements: Measurement[];
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2
    : (sorted[middle] ?? 0);
}

function numbersIn(text: string | null): number[] {
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

async function measure(page: Page, plants: number): Promise<Measurement> {
  await page.goto(`/?scene=stress&plants=${plants}`);
  await expect(page.getByTestId("scene-status")).toContainText(`${plants + 2} entities`);
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
    plants,
    medianFramesPerSecond: Math.round(median(rates)),
    medianFrameMs: Number(median(frameTimes).toFixed(1)),
    worstFrameMs: worst,
    drawCalls,
    triangles,
  };
}

function compare(latest: Benchmark, baseline: Benchmark | null): string {
  const lines = [
    `renderer: ${latest.renderer}`,
    "plants   fps (baseline)   frame ms (baseline)   worst ms   draw calls",
  ];
  for (const now of latest.measurements) {
    const then = baseline?.measurements.find((m) => m.plants === now.plants);
    const was = (value: number | undefined) => (value === undefined ? "—" : String(value));
    lines.push(
      `${String(now.plants).padStart(7)}  ${String(now.medianFramesPerSecond).padStart(4)} (${was(then?.medianFramesPerSecond)})` +
        `   ${String(now.medianFrameMs).padStart(5)} (${was(then?.medianFrameMs)})` +
        `       ${String(now.worstFrameMs).padStart(5)}   ${now.drawCalls}`,
    );
  }
  return lines.join("\n");
}

test("the stress scene's frame rate, at several sizes, while orbiting", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  const benchmark: Benchmark = {
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
    measurements: [],
  };
  for (const plants of SIZES) {
    benchmark.measurements.push(await measure(page, plants));
  }

  mkdirSync(new URL(".", LATEST), { recursive: true });
  writeFileSync(LATEST, `${JSON.stringify(benchmark, null, 2)}\n`);
  if (process.env.RECORD_BENCHMARK) {
    writeFileSync(BASELINE, `${JSON.stringify(benchmark, null, 2)}\n`);
  }
  const baseline: Benchmark | null = existsSync(BASELINE)
    ? JSON.parse(readFileSync(BASELINE, "utf8"))
    : null;
  console.log(compare(benchmark, baseline));

  // A record, not a gate: only a scene that failed to draw fails the benchmark.
  for (const measurement of benchmark.measurements) {
    expect(measurement.medianFramesPerSecond).toBeGreaterThan(0);
  }
});
