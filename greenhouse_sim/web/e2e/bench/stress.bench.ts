import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { type Orbited, orbit, type RanOn, ranOn } from "./measuring";

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

interface Measurement extends Orbited {
  plants: number;
}

interface Benchmark extends RanOn {
  measurements: Measurement[];
}

async function measure(page: Page, plants: number): Promise<Measurement> {
  await page.goto(`/?scene=stress&plants=${plants}`);
  await expect(page.getByTestId("scene-status")).toContainText(`${plants + 2} entities`);
  return { plants, ...(await orbit(page)) };
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
  const benchmark: Benchmark = { ...(await ranOn(page, browser)), measurements: [] };
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
