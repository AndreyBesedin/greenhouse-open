// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render, said } from "../testing/render";
import type { PositionState } from "./position";
import { ReplayHeader, runSubtitle } from "./ReplayHeader";

function position(more: Partial<PositionState> = {}): PositionState {
  return {
    position_id: "p1",
    scenario_id: "reference_greenhouse",
    run_id: "run-1",
    epoch: 3,
    layout: "default",
    seed: 2,
    status: "running",
    started_at: "2026-03-01T00:00:00Z",
    simulated_now: "2026-03-01T00:00:00Z",
    time_s: 0,
    day: 0,
    playing: false,
    following: false,
    seconds_per_day: 10,
    frontier_s: DAY_S,
    duration_s: 120 * DAY_S,
    start_s: 0,
    fork: null,
    targets: [],
    commands: [],
    crop: [],
    ...more,
  };
}

describe("the replay's header", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  it("has the way home, the run's name, its seed and epoch, and its state in words", () => {
    rendered = render(
      <ReplayHeader name="Reference greenhouse" position={position()} otherRunsHref="/#runs" />,
    );
    const { container } = rendered;

    expect(container.querySelector("h1")?.textContent).toBe("Reference greenhouse");
    expect(said(container, "replay-subtitle")).toBe("seed 2 · epoch 3 · everything kept");
    expect(said(container, "replay-status")).toBe("Running");
    expect(container.querySelector('[data-testid="home-button"]')?.textContent).toContain("Home");
    expect(container.textContent).not.toContain("Scenarios");
  });

  it("links to the run's other runs", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position()}
        otherRunsHref="/#runs=reference_greenhouse"
      />,
    );
    const other = [...rendered.container.querySelectorAll("a")].find(
      (link) => link.textContent === "Other runs",
    );

    expect(other?.getAttribute("href")).toBe("/#runs=reference_greenhouse");
    // Until the scenarios say its name, the scenario's identifier stands for it.
    expect(rendered.container.querySelector("h1")?.textContent).toBe("reference_greenhouse");
  });

  it("says each state of a run as a word", () => {
    for (const [status, word] of [
      ["finished", "Finished"],
      ["interrupted", "Interrupted"],
      ["failed", "Failed"],
    ] as const) {
      rendered = render(
        <ReplayHeader name={null} position={position({ status })} otherRunsHref="/" />,
      );
      expect(said(rendered.container, "replay-status")).toBe(word);
      rendered.unmount();
    }
  });

  it("says a run of the scenario's own seed without a number", () => {
    expect(runSubtitle(position({ seed: null }))).toBe(
      "the scenario's seed · epoch 3 · everything kept",
    );
  });
});
