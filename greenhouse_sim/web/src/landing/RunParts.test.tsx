// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import { DAMAGED_NOTE, RunStatus, STOPPING_NOTE } from "./RunParts";
import type { StoredRun } from "./storedRuns";

function run(more: Partial<StoredRun>): StoredRun {
  return {
    run_id: "reference_greenhouse-climate-abc",
    epoch: 0,
    scenario_id: "reference_greenhouse",
    seed: 1,
    layout: "default",
    status: "finished",
    paused: false,
    frontier_s: 120 * DAY_S,
    duration_s: 120 * DAY_S,
    progress: 1,
    created_at: "2026-10-28T09:30:00Z",
    size_bytes: 0,
    start_s: 0,
    fork: null,
    stopping: false,
    damaged: false,
    days_computed: 0,
    cpu_s: null,
    peak_memory_bytes: null,
    wall_s: null,
    past_limit: false,
    reason: null,
    ...more,
  };
}

describe("a run's status", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  /** The chip drawn for `stored`: its classes, words, and what its title says. */
  function chip(stored: StoredRun) {
    shown?.unmount();
    shown = render(<RunStatus run={stored} />);
    const element = shown.container.firstElementChild as HTMLElement;
    return { classes: element.className, words: element.textContent, title: element.title };
  }

  it("is the design system's chip, in the tone of its status, with the page's classes beside it", () => {
    expect(chip(run({ status: "queued" }))).toEqual({
      classes: "ds-status-chip ds-status-chip-active landing-status landing-status-queued",
      words: "Queued",
      title: "",
    });
    expect(chip(run({ status: "running" })).classes).toBe(
      "ds-status-chip ds-status-chip-active landing-status landing-status-running",
    );
    expect(chip(run({ status: "finished" }))).toEqual({
      classes: "ds-status-chip landing-status landing-status-finished",
      words: "Finished",
      title: "",
    });
    expect(chip(run({ status: "failed" })).classes).toBe(
      "ds-status-chip ds-status-chip-problem landing-status landing-status-failed",
    );
    expect(chip(run({ status: "interrupted" })).classes).toBe(
      "ds-status-chip ds-status-chip-problem landing-status landing-status-interrupted",
    );
  });

  it("says Paused of a run whose playback holds its clock, in its status's tone", () => {
    expect(chip(run({ status: "running", paused: true }))).toEqual({
      classes: "ds-status-chip ds-status-chip-active landing-status landing-status-running",
      words: "Paused",
      title: "",
    });
  });

  it("says Stopping, and why, of a run asked to stop", () => {
    expect(chip(run({ status: "running", stopping: true }))).toEqual({
      classes: "ds-status-chip ds-status-chip-active landing-status landing-status-running",
      words: `Stopping ${STOPPING_NOTE}`,
      title: STOPPING_NOTE,
    });
  });

  it("says Damaged of a run with files missing, whatever its status, as a problem", () => {
    expect(chip(run({ status: "finished", damaged: true, stopping: true }))).toEqual({
      classes: "ds-status-chip ds-status-chip-problem landing-status landing-status-failed",
      words: `Damaged ${DAMAGED_NOTE}`,
      title: DAMAGED_NOTE,
    });
  });
});
