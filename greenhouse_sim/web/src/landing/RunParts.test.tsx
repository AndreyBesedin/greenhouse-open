// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import { replayAddress } from "./paths";
import { DAMAGED_NOTE, FOLLOWS_NOTE, ReplayLink, RunStatus, STOPPING_NOTE } from "./RunParts";
import type { StoredRun } from "./storedRuns";

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

  it("is the design system's chip, in the tone of its status, placed by the list's class", () => {
    expect(chip(run({ status: "queued" }))).toEqual({
      classes: "ds-status-chip ds-status-chip-active landing-run-status",
      words: "Queued",
      title: "",
    });
    expect(chip(run({ status: "running" })).classes).toBe(
      "ds-status-chip ds-status-chip-active landing-run-status",
    );
    expect(chip(run({ status: "finished" }))).toEqual({
      classes: "ds-status-chip landing-run-status",
      words: "Finished",
      title: "",
    });
    expect(chip(run({ status: "failed" })).classes).toBe(
      "ds-status-chip ds-status-chip-problem landing-run-status",
    );
    expect(chip(run({ status: "interrupted" })).classes).toBe(
      "ds-status-chip ds-status-chip-problem landing-run-status",
    );
  });

  it("says Stopping, and why, of a run asked to stop", () => {
    expect(chip(run({ status: "running", stopping: true }))).toEqual({
      classes: "ds-status-chip ds-status-chip-active landing-run-status",
      words: `Stopping ${STOPPING_NOTE}`,
      title: STOPPING_NOTE,
    });
  });

  it("says Damaged of a run with files missing, whatever its status, as a problem", () => {
    expect(chip(run({ status: "finished", damaged: true, stopping: true }))).toEqual({
      classes: "ds-status-chip ds-status-chip-problem landing-run-status",
      words: `Damaged ${DAMAGED_NOTE}`,
      title: DAMAGED_NOTE,
    });
  });
});

describe("a run's replay, the one way to watch it", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  /** Where the link drawn for `stored` goes and what it says on hover, or null without one. */
  function link(stored: StoredRun) {
    shown?.unmount();
    shown = render(<ReplayLink run={stored} />);
    const found = shown.container.querySelector("a");
    return found === null ? null : { href: found.getAttribute("href"), title: found.title };
  }

  it("follows the newest day of a run being computed, and says so", () => {
    for (const status of ["queued", "running"] as const) {
      expect(link(run({ status, epoch: 2 }))).toEqual({
        href: replayAddress("reference_greenhouse-climate-abc", 2, true),
        title: FOLLOWS_NOTE,
      });
    }
  });

  it("opens a run computed no longer at its start", () => {
    for (const status of ["finished", "interrupted", "failed"] as const) {
      expect(link(run({ status }))).toEqual({
        href: replayAddress("reference_greenhouse-climate-abc", 0),
        title: "",
      });
    }
  });

  it("is not there for a run with files missing", () => {
    expect(link(run({ status: "running", damaged: true }))).toBeNull();
  });
});
