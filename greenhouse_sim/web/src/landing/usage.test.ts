import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import type { StoredRun } from "./storedRuns";
import { daysText, durationText, NOT_MEASURED, NOT_MEASURED_NOTE, usageFigures } from "./usage";

function run(more: Partial<StoredRun>): StoredRun {
  return {
    run_id: "reference_greenhouse-climate-abc",
    epoch: 0,
    scenario_id: "reference_greenhouse",
    seed: 1,
    layout: "default",
    weather: null,
    status: "finished",
    frontier_s: 120 * DAY_S,
    duration_s: 120 * DAY_S,
    progress: 1,
    created_at: null,
    size_bytes: 20_647_025,
    start_s: 0,
    fork: null,
    stopping: false,
    damaged: false,
    days_computed: 120,
    cpu_s: null,
    peak_memory_bytes: null,
    wall_s: null,
    past_limit: false,
    reason: null,
    ...more,
  };
}

describe("what a run used, in words", () => {
  it("says a length of time in the units that read best", () => {
    expect([0, 4.24, 9.96, 42.4, 60, 1357, 3600, 3660, 11_100].map(durationText)).toEqual([
      "0.0 s",
      "4.2 s",
      "10 s",
      "42 s",
      "1 min",
      "22 min 37 s",
      "1 h",
      "1 h 1 min",
      "3 h 5 min",
    ]);
  });

  it("says days computed whole as they are, a part of one to a tenth", () => {
    expect([0, 1, 120, 2.5, 119.99999999].map(daysText)).toEqual([
      "0 days",
      "1 day",
      "120 days",
      "2.5 days",
      "120 days",
    ]);
  });

  it("says each figure of a run its workers measured, in a person's units", () => {
    // The reference run's report (P18.2): 20,647,025 bytes, 1,357 s of CPU, 328 MB.
    const measured = run({ cpu_s: 1357, peak_memory_bytes: 328_000_000, wall_s: 2640 });

    expect(usageFigures(measured)).toEqual([
      { label: "Kept", value: "20.6 MB", measured: true },
      { label: "Computed", value: "120 days", measured: true },
      { label: "CPU", value: "22 min 37 s", measured: true },
      { label: "Peak memory", value: "328.0 MB", measured: true },
      { label: "Wall time", value: "44 min", measured: true },
    ]);
  });

  it("says a figure no worker measured is not measured, and not zero", () => {
    const figures = usageFigures(run({ days_computed: 3 }));
    const byLabel = new Map(figures.map((each) => [each.label, each]));

    for (const label of ["CPU", "Peak memory", "Wall time"]) {
      expect(byLabel.get(label)).toEqual({ label, value: NOT_MEASURED, measured: false });
    }
    // What the store says of itself is always known.
    expect(byLabel.get("Computed")?.value).toBe("3 days");
    expect(byLabel.get("Kept")?.measured).toBe(true);
    expect(NOT_MEASURED_NOTE).toContain("not zero");
  });

  it("tells a figure of zero from one not measured", () => {
    const figures = usageFigures(run({ cpu_s: 0, peak_memory_bytes: 0, wall_s: 0 }));

    expect(figures.map((each) => each.value).slice(2)).toEqual(["0.0 s", "0 B", "0.0 s"]);
    expect(figures.every((each) => each.measured)).toBe(true);
  });
});
