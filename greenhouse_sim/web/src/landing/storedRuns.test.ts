import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import {
  isComputing,
  KEPT_SIZE_NOTE,
  keptText,
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
    start_s: 0,
    fork: null,
    stopping: false,
    damaged: false,
    days_computed: 0,
    cpu_s: null,
    peak_memory_bytes: null,
    reason: null,
    ...more,
  };
}

describe("the runs the simulator has kept", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

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

  it("says how many runs are kept and the size of their objects in all", () => {
    const MB = 1024 * 1024;
    const runs = [
      run({ size_bytes: 8 * MB }),
      run({ epoch: 1, size_bytes: 4 * MB + MB / 2 }),
      run({ epoch: 2, size_bytes: 0 }),
    ];

    expect(keptText(runs)).toBe("3 runs kept, 12.5 MB");
  });

  it("says one run kept in the singular, and its size in the unit that reads best", () => {
    expect(keptText([run({ size_bytes: 1500 })])).toBe("1 run kept, 1 kB");
    expect(keptText([run({ size_bytes: 12 })])).toBe("1 run kept, 12 B");
  });

  it("says nothing when none is kept, which the list says in its own words", () => {
    expect(keptText([])).toBeNull();
  });

  it("says that the size is of the runs' objects, not of the disk", () => {
    expect(KEPT_SIZE_NOTE).toContain("not of the disk");
  });

  it("writes sizes the same wherever they are read", () => {
    expect([512, 2048, 8 * 1024 * 1024].map(sizeText)).toEqual(["512 B", "2 kB", "8.0 MB"]);
  });

  it("writes a run's start as the day it was where it is read", () => {
    const justAfterMidnightInParis = run({ created_at: "2026-11-03T23:25:00Z" });
    vi.stubEnv("TZ", "Europe/Paris");
    expect(startedText(justAfterMidnightInParis)).toBe("Nov 4");
    vi.stubEnv("TZ", "America/New_York");
    expect(startedText(justAfterMidnightInParis)).toBe("Nov 3");
    expect(startedText(run({ created_at: "2026-11-04T02:00:00Z" }))).toBe("Nov 3");
  });

  it("writes no start day when the start is not known", () => {
    expect(startedText(run({ created_at: null }))).toBe("");
    expect(startedText(run({ created_at: "not a date" }))).toBe("");
  });
});
