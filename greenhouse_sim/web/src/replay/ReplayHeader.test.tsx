// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

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

const noFork = () => undefined;

describe("the replay's header", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  it("has the way home, the run's name, its seed and epoch, and its state in words", () => {
    rendered = render(
      <ReplayHeader
        name="Reference greenhouse"
        position={position()}
        otherRunsHref="/#runs"
        onFork={noFork}
      />,
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
        onFork={noFork}
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
        <ReplayHeader
          name={null}
          position={position({ status })}
          otherRunsHref="/"
          onFork={noFork}
        />,
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

  it("forks the run from the moment shown, and says it is at it", () => {
    const onFork = vi.fn();
    rendered = render(
      <ReplayHeader name={null} position={position()} otherRunsHref="/" onFork={onFork} />,
    );
    const button = rendered.container.querySelector<HTMLButtonElement>(
      '[data-testid="replay-fork"]',
    );

    expect(button?.textContent).toBe("Fork from here");
    button?.click();
    expect(onFork).toHaveBeenCalledOnce();
  });

  it("offers no fork at the run's end, and says why", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ time_s: 120 * DAY_S })}
        otherRunsHref="/"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(
      container.querySelector<HTMLButtonElement>('[data-testid="replay-fork"]')?.disabled,
    ).toBe(true);
    expect(said(container, "replay-no-fork")).toMatch(/ends here/);
  });

  it("says why a fork was refused, and while one is on its way", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position()}
        otherRunsHref="/"
        forking
        forkRefused="no room"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(said(container, "replay-fork-refused")).toBe("This run could not be forked: no room.");
    const button = container.querySelector<HTMLButtonElement>('[data-testid="replay-fork"]');
    expect(button?.disabled).toBe(true);
    expect(button?.textContent).toBe("Forking…");
  });

  it("says what a fork came from, and links to it", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({
          fork: {
            run_id: "parent run",
            epoch: 1,
            at_s: DAY_S * 1.5,
            start_s: DAY_S,
            digest: null,
            checkpoint_sha256: null,
            inherited: 0,
            layout: null,
          },
        })}
        otherRunsHref="/"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(said(container, "replay-subtitle")).toBe(
      "seed 2 · epoch 3 · everything kept · forked from epoch 1 at Day 2, 12:00",
    );
    const parent = [...container.querySelectorAll("a")].find(
      (link) => link.textContent === "The run it came from",
    );
    expect(parent?.getAttribute("href")).toBe("/replay?run=parent%20run&epoch=1");
  });
});
