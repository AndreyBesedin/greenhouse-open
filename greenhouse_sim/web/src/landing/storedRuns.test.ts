import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import {
  isComputing,
  loadStoredRuns,
  parseStoredRuns,
  progressShare,
  progressText,
  runCounts,
  runCountText,
  STATUS_LABEL,
  type StoredRun,
  sizeText,
  startedText,
} from "./storedRuns";

function run(more: Partial<StoredRun> = {}): StoredRun {
  return {
    run_id: "reference_greenhouse-climate-abc",
    epoch: 0,
    scenario_id: "reference_greenhouse",
    seed: 2,
    layout: "default",
    status: "running",
    frontier_s: 41 * DAY_S,
    duration_s: 120 * DAY_S,
    progress: 41 / 120,
    created_at: "2026-10-28T09:30:00Z",
    size_bytes: 8 * 1024 * 1024,
    ...more,
  };
}

describe("the runs the simulator has kept", () => {
  it("reads a list of runs as the simulator sends them", () => {
    expect(parseStoredRuns([run(), run({ seed: null, created_at: null })])).toHaveLength(2);
  });

  it("refuses a body that is not a list, or a run that is not one", () => {
    expect(() => parseStoredRuns({})).toThrow("expected a list of runs");
    expect(() => parseStoredRuns([run(), { run_id: "x" }])).toThrow("run 1 is not a stored run");
    expect(() => parseStoredRuns([{ ...run(), status: "paused" }])).toThrow("run 0");
  });

  it("loads them, and says why when it cannot", async () => {
    const sent = (body: unknown, status = 200) =>
      (() => Promise.resolve(new Response(JSON.stringify(body), { status }))) as typeof fetch;

    expect(await loadStoredRuns(sent([run()]))).toEqual({ status: "loaded", runs: [run()] });
    expect(await loadStoredRuns(sent({}, 500))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 500",
    });
    const unreachable = (() => Promise.reject(new Error("offline"))) as typeof fetch;
    expect(await loadStoredRuns(unreachable)).toEqual({
      status: "unavailable",
      reason: "offline",
    });
  });

  it("counts the runs of each scenario, in words", () => {
    const counts = runCounts([run(), run({ epoch: 1 }), run({ scenario_id: "tomgro_house" })]);
    expect(counts.get("reference_greenhouse")).toBe(2);
    expect(counts.get("tomgro_house")).toBe(1);
    expect([0, 1, 2].map(runCountText)).toEqual(["no runs", "1 run", "2 runs"]);
  });

  it("says how far a run is, in whole days, whether or not its length is known", () => {
    expect(progressText(run())).toBe("41 of 120 days");
    expect(progressText(run({ frontier_s: 41.9 * DAY_S }))).toBe("41 of 120 days");
    expect(progressText(run({ duration_s: null, progress: null }))).toBe("41 days");
    expect(progressShare(run())).toBeCloseTo(41 / 120);
    expect(progressShare(run({ progress: null }))).toBe(0);
    expect(progressShare(run({ progress: 1.2 }))).toBe(1);
  });

  it("names every status in words, and tells a run still computing from one that is not", () => {
    expect(Object.values(STATUS_LABEL)).toEqual([
      "Queued",
      "Running",
      "Finished",
      "Failed",
      "Interrupted",
    ]);
    expect(
      (["queued", "running", "finished", "failed", "interrupted"] as const).map((status) =>
        isComputing(run({ status })),
      ),
    ).toEqual([true, true, false, false, false]);
  });

  it("writes sizes and start days the same wherever they are read", () => {
    expect([512, 2048, 8 * 1024 * 1024].map(sizeText)).toEqual(["512 B", "2 kB", "8.0 MB"]);
    expect(startedText(run())).toBe("Oct 28");
    expect(startedText(run({ created_at: "2026-10-28T23:30:00-05:00" }))).toBe("Oct 29");
    expect(startedText(run({ created_at: null }))).toBe("");
    expect(startedText(run({ created_at: "not a date" }))).toBe("");
  });
});
