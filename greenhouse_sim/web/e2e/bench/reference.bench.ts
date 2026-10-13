import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { numbersIn, type Orbited, orbit, type RanOn, ranOn } from "./measuring";

/**
 * Measures the reference greenhouse at its fullest crop (P09.8): its climate
 * at the end of its season, every day lived, as the viewer draws it, while
 * the camera orbits; and how long the simulator took to give each part of
 * it, as its API says (`Server-Timing`). Compared with the recorded
 * baseline, as the stress scene's is.
 *
 *     npm run bench                      # measure and compare
 *     RECORD_BENCHMARK=1 npm run bench   # measure and record as the baseline
 */

const BASELINE = new URL("../../benchmarks/reference.json", import.meta.url);
const LATEST = new URL("../../test-results/bench/reference.json", import.meta.url);
// The season's end: 120 days, each lived. The simulator works the run out
// from its kept opening day, day 80, its air and its crop, and the same run
// all off beside it: minutes, on a laptop.
const SEASON_DAYS = 120;
const DAY_S = 86_400;
const SEASON_END = `/?scenario=reference_greenhouse&field=climate&t=${SEASON_DAYS * DAY_S}`;
const LOADING_TIMEOUT_MS = 600_000;

interface Benchmark extends RanOn, Orbited {
  scene: string;
  entities: number;
  /** What the simulator took to answer each request the view made, the
   * longest first, in milliseconds. */
  simulatorMs: Record<string, number>;
}

function compare(latest: Benchmark, baseline: Benchmark | null): string {
  const was = (value: number | undefined) => (value === undefined ? "—" : String(value));
  return [
    `renderer: ${latest.renderer}`,
    `${latest.scene}: ${latest.entities} entities`,
    `fps ${latest.medianFramesPerSecond} (${was(baseline?.medianFramesPerSecond)}), ` +
      `frame ${latest.medianFrameMs} ms (${was(baseline?.medianFrameMs)}), ` +
      `worst ${latest.worstFrameMs} ms, ${latest.drawCalls} draw calls`,
    "simulator, ms:",
    ...Object.entries(latest.simulatorMs).map(
      ([path, ms]) => `  ${path}: ${ms} (${was(baseline?.simulatorMs[path])})`,
    ),
  ].join("\n");
}

test("the reference greenhouse at its fullest crop, while orbiting", async ({ page, browser }) => {
  test.setTimeout(LOADING_TIMEOUT_MS + 60_000);
  await page.goto(SEASON_END);
  await expect(page.getByTestId("climate-time")).toHaveText(`day ${SEASON_DAYS - 1}, 24 h 00 min`);
  // Its crop as it stands at the season's end, its field over it.
  await expect(page.getByTestId("scene-status")).toContainText(`day ${SEASON_DAYS},`, {
    timeout: LOADING_TIMEOUT_MS,
  });
  await expect(page.getByTestId("field-legend-quantity")).toBeVisible({
    timeout: LOADING_TIMEOUT_MS,
  });
  const [, entities = 0] = numbersIn(await page.getByTestId("scene-status").textContent());

  const orbited = await orbit(page);
  const simulatorMs = await page.evaluate(() =>
    Object.fromEntries(
      performance
        .getEntriesByType("resource")
        .flatMap((entry) => {
          const timing = entry as PerformanceResourceTiming;
          const sim = timing.serverTiming.find((said) => said.name === "sim");
          const path = new URL(timing.name).pathname.replace(/^\/api\/scenarios\/[^/]+\//, "");
          return sim === undefined ? [] : [[path, Math.round(sim.duration)] as const];
        })
        .sort(([, a], [, b]) => b - a),
    ),
  );
  const benchmark: Benchmark = {
    ...(await ranOn(page, browser)),
    scene: `reference_greenhouse at day ${SEASON_DAYS}'s end, its climate drawn`,
    entities,
    ...orbited,
    simulatorMs,
  };

  mkdirSync(new URL(".", LATEST), { recursive: true });
  writeFileSync(LATEST, `${JSON.stringify(benchmark, null, 2)}\n`);
  if (process.env.RECORD_BENCHMARK) {
    writeFileSync(BASELINE, `${JSON.stringify(benchmark, null, 2)}\n`);
  }
  const baseline: Benchmark | null = existsSync(BASELINE)
    ? JSON.parse(readFileSync(BASELINE, "utf8"))
    : null;
  console.log(compare(benchmark, baseline));

  // A record, not a gate: only a scene that failed to draw fails it.
  expect(benchmark.medianFramesPerSecond).toBeGreaterThan(0);
});
