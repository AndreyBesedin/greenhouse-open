// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { click, button as named, type Rendered, render, said } from "../testing/render";
import type { PositionState } from "./position";
import { ReplayHeader, runSubtitle, STATUS_NAME } from "./ReplayHeader";
import { WHAT_A_FORK_DOES } from "./useForkQuestion";

const FORK: PositionState["fork"] = {
  run_id: "parent run",
  epoch: 1,
  at_s: DAY_S * 1.5,
  start_s: DAY_S,
  digest: null,
  checkpoint_sha256: null,
  inherited: 0,
  layout: null,
};

function position(more: Partial<PositionState> = {}): PositionState {
  return {
    position_id: "p1",
    scenario_id: "reference_greenhouse",
    run_id: "run-1",
    epoch: 3,
    layout: "default",
    seed: 2,
    weather: null,
    status: "running",
    started_at: "2026-03-01T00:00:00Z",
    simulated_now: "2026-03-01T00:00:00Z",
    time_s: 0,
    day: 0,
    playing: false,
    following: false,
    parent_kept: false,
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

/** The run's status, as whoever hears the page finds it: by its role and name. */
function statusChip(within: ParentNode): Element | null {
  return within.querySelector(`[role="status"][aria-label="${STATUS_NAME}"]`);
}

function statusOf(within: ParentNode): string | null {
  return statusChip(within)?.textContent ?? null;
}

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
    expect(statusOf(container)).toBe("Running");
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

  it("says each state of a run as a word, in the chip of the start page's runs", () => {
    for (const [status, word, tone] of [
      ["queued", "Queued", "ds-status-chip ds-status-chip-active"],
      ["finished", "Finished", "ds-status-chip"],
      ["interrupted", "Interrupted", "ds-status-chip ds-status-chip-problem"],
      ["failed", "Failed", "ds-status-chip ds-status-chip-problem"],
    ] as const) {
      rendered = render(
        <ReplayHeader
          name={null}
          position={position({ status })}
          otherRunsHref="/"
          onFork={noFork}
        />,
      );
      expect(statusOf(rendered.container)).toBe(word);
      expect(statusChip(rendered.container)?.className).toBe(tone);
      rendered.unmount();
    }
  });

  it("says a run of the scenario's own seed without a number", () => {
    expect(runSubtitle(position({ seed: null }))).toBe(
      "the scenario's seed · epoch 3 · everything kept",
    );
  });

  it("says why a failed run failed, and keeps only what it computed", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ status: "failed" })}
        otherRunsHref="/"
        failure="its worker ran out of memory"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(said(container, "replay-failed")).toBe("This run failed: its worker ran out of memory.");
    expect(said(container, "replay-subtitle")).toBe("seed 2 · epoch 3 · kept to where it failed");
  });

  it("says a run failed while why is on its way, and nothing of one that did not", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ status: "failed" })}
        otherRunsHref="/"
        onFork={noFork}
      />,
    );
    expect(said(rendered.container, "replay-failed")).toBe("This run failed.");
    rendered.unmount();

    rendered = render(
      <ReplayHeader
        name={null}
        position={position()}
        otherRunsHref="/"
        failure="ignored"
        onFork={noFork}
      />,
    );
    expect(rendered.container.querySelector('[data-testid="replay-failed"]')).toBeNull();
  });

  describe("a fork from the moment shown", () => {
    function shown(onFork: () => void) {
      rendered = render(
        <ReplayHeader name={null} position={position()} otherRunsHref="/" onFork={onFork} />,
      );
      const { container } = rendered;
      const pressed = container.querySelector('[data-testid="replay-fork"]') as HTMLButtonElement;
      return { container, pressed };
    }

    it("says what it does first, and is made only once that is confirmed", () => {
      const onFork = vi.fn();
      const { container, pressed } = shown(onFork);
      expect(pressed.textContent).toBe("Fork from here");
      expect(container.querySelector('[data-testid="fork-question"]')).toBeNull();

      click(pressed);

      expect(onFork).not.toHaveBeenCalled();
      expect(said(container, "fork-question")).toContain(WHAT_A_FORK_DOES);
      // Ready to be answered from the keyboard, on the answer the page is drawn to lead to.
      expect(document.activeElement).toBe(named(container, "Make the fork"));
      expect(named(container, "Make the fork").className).toBe("ds-button ds-button-primary");
      expect(named(container, "Cancel").className).toBe("ds-button");

      click(named(container, "Make the fork"));

      expect(onFork).toHaveBeenCalledOnce();
      expect(container.querySelector('[data-testid="fork-question"]')).toBeNull();
    });

    it("is not made if cancelled, with the keyboard back on what was pressed", () => {
      const onFork = vi.fn();
      const { container, pressed } = shown(onFork);

      click(pressed);
      click(named(container, "Cancel"));

      expect(onFork).not.toHaveBeenCalled();
      expect(container.querySelector('[data-testid="fork-question"]')).toBeNull();
      expect(document.activeElement).toBe(pressed);
    });

    it("is cancelled by Escape, which is not left for the view", () => {
      const onFork = vi.fn();
      const { container, pressed } = shown(onFork);

      click(pressed);
      const pressedKey = new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      });
      act(() => document.activeElement?.dispatchEvent(pressedKey));

      expect(onFork).not.toHaveBeenCalled();
      expect(pressedKey.defaultPrevented).toBe(true);
      expect(container.querySelector('[data-testid="fork-question"]')).toBeNull();
      expect(document.activeElement).toBe(pressed);
    });

    it("takes the moment shown when it was asked for, while the replay plays on", () => {
      const fromThen = vi.fn();
      const fromNow = vi.fn();
      const { container, pressed } = shown(fromThen);

      click(pressed);
      rendered?.rerender(
        <ReplayHeader
          name={null}
          position={position({ time_s: 2 * DAY_S })}
          otherRunsHref="/"
          onFork={fromNow}
        />,
      );
      click(named(container, "Make the fork"));

      expect(fromThen).toHaveBeenCalledOnce();
      expect(fromNow).not.toHaveBeenCalled();
    });
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
        position={position({ fork: FORK, parent_kept: true })}
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

  it("keeps what a fork says of the run it came from, with no link once that is deleted", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ fork: FORK, parent_kept: false })}
        otherRunsHref="/"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(said(container, "replay-subtitle")).toContain("forked from epoch 1 at Day 2, 12:00");
    expect([...container.querySelectorAll("a")].map((link) => link.textContent)).not.toContain(
      "The run it came from",
    );
  });
});
