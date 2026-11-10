// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { HOME_NOTE } from "../landing/HomeButton";
import { STOP_AND_DELETE_NOTE, STOPS_FIRST } from "../landing/RunDelete";
import type { StoredRun } from "../landing/storedRuns";
import { click, button as named, type Rendered, render, said } from "../testing/render";
import type { PositionState } from "./position";
import { FORK_NOTE, PARENT_NOTE, ReplayHeader, runSubtitle, STATUS_NAME } from "./ReplayHeader";
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

/** The run as the simulator answers a stop of it. */
function stored(more: Partial<StoredRun>): StoredRun {
  return {
    run_id: "run-1",
    epoch: 3,
    scenario_id: "reference_greenhouse",
    seed: 2,
    layout: "default",
    weather: null,
    status: "interrupted",
    frontier_s: DAY_S,
    duration_s: 120 * DAY_S,
    progress: 1 / 120,
    created_at: "2026-03-01T00:00:00Z",
    size_bytes: 1024,
    start_s: 0,
    fork: null,
    stopping: false,
    damaged: false,
    days_computed: 1,
    cpu_s: null,
    peak_memory_bytes: null,
    wall_s: null,
    past_limit: false,
    reason: null,
    ...more,
  };
}

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
const stays = () => undefined;

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
        onDeleted={stays}
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(container.querySelector("h1")?.textContent).toBe("Run of Reference greenhouse");
    expect(said(container, "replay-subtitle")).toBe("seed 2 · epoch 3 · everything kept");
    expect(statusOf(container)).toBe("Running");
    expect(container.querySelector('[data-testid="home-button"]')?.textContent).toContain("Home");
    expect(container.textContent).not.toContain("Scenarios");
  });

  it("names the scenario by its identifier until the scenarios say its name", () => {
    rendered = render(
      <ReplayHeader name={null} position={position()} onDeleted={stays} onFork={noFork} />,
    );
    expect(rendered.container.querySelector("h1")?.textContent).toBe("Run of reference_greenhouse");
  });

  it("says what each of its buttons does on hover, Fork first", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ fork: FORK, parent_kept: true })}
        onDeleted={stays}
        onFork={noFork}
      />,
    );
    const { container } = rendered;
    expect(container.querySelector('[data-testid="replay-fork"]')?.getAttribute("title")).toBe(
      FORK_NOTE,
    );
    // A run being computed is stopped before it is deleted, and says so.
    expect(named(container, "Delete this run").title).toBe(STOP_AND_DELETE_NOTE);
    expect(container.querySelector('[data-testid="home-button"]')?.getAttribute("title")).toBe(
      HOME_NOTE,
    );
    const parent = [...container.querySelectorAll("a")].find(
      (link) => link.textContent === "The run it came from",
    );
    expect(parent?.title).toBe(PARENT_NOTE);
  });

  describe("its Delete, in place of the way to its other runs", () => {
    afterEach(() => vi.unstubAllGlobals());

    /** The header over a run of `status`, the simulator answering a delete with
     * `answer`, and a stop with `stopped`. */
    function shown(status: PositionState["status"], answer: Response, stopped?: Response) {
      const asked = vi.fn(async (url: string, _init?: RequestInit) =>
        url.endsWith("/stop") && stopped !== undefined ? stopped : answer.clone(),
      );
      vi.stubGlobal("fetch", asked);
      const onDeleted = vi.fn();
      rendered = render(
        <ReplayHeader
          name="Reference greenhouse"
          position={position({ status })}
          onDeleted={onDeleted}
          onFork={noFork}
        />,
      );
      return { container: rendered.container, asked, onDeleted };
    }

    async function confirmed(container: HTMLElement): Promise<void> {
      click(named(container, "Delete this run"));
      // Asked again, with the keyboard on the answer that loses nothing.
      expect(document.activeElement).toBe(named(container, "Keep it"));
      await act(async () => named(container, "Delete this run").click());
    }

    it("asks again, then deletes the run, and the page goes with it", async () => {
      const { container, asked, onDeleted } = shown("finished", new Response(null));

      click(named(container, "Delete this run"));
      expect(asked).not.toHaveBeenCalled();
      click(named(container, "Keep it"));
      expect(asked).not.toHaveBeenCalled();
      await confirmed(container);

      expect(asked).toHaveBeenCalledWith("/api/runs/run-1/epochs/3/delete", { method: "POST" });
      expect(onDeleted).toHaveBeenCalledOnce();
      expect(container.querySelector('[data-testid="replay-delete-refused"]')).toBeNull();
    });

    it("says first that a run being computed is stopped, then stops and deletes it", async () => {
      const deletes = [new Response(null, { status: 409 }), new Response(null)];
      const asked = vi.fn(async (url: string, _init?: RequestInit) =>
        url.endsWith("/stop")
          ? Response.json(stored({ status: "interrupted" }))
          : (deletes.shift() ?? new Response(null)),
      );
      vi.stubGlobal("fetch", asked);
      const onDeleted = vi.fn();
      rendered = render(
        <ReplayHeader
          name="Reference greenhouse"
          position={position({ status: "running" })}
          onDeleted={onDeleted}
          onFork={noFork}
        />,
      );
      const { container } = rendered;

      click(named(container, "Delete this run"));
      expect(container.querySelector(".landing-confirm-note")?.textContent).toBe(STOPS_FIRST);
      await act(async () => named(container, "Stop and delete this run").click());

      expect(asked.mock.calls.map(([url]) => url)).toEqual([
        "/api/runs/run-1/epochs/3/delete",
        "/api/runs/run-1/epochs/3/stop",
        "/api/runs/run-1/epochs/3/delete",
      ]);
      expect(onDeleted).toHaveBeenCalledOnce();
    });

    it("says a run whose worker has not stopped yet is stopping, and stays", async () => {
      const { container, onDeleted } = shown(
        "running",
        new Response(null, { status: 409 }),
        Response.json(stored({ status: "running", stopping: true })),
      );

      click(named(container, "Delete this run"));
      await act(async () => named(container, "Stop and delete this run").click());

      expect(onDeleted).not.toHaveBeenCalled();
      expect(said(container, "replay-delete-refused")).toBe(
        "This run is stopping: it can be deleted once it reads Interrupted.",
      );
      // Once the run reads otherwise, what was said of it goes.
      rendered?.rerender(
        <ReplayHeader
          name="Reference greenhouse"
          position={position({ status: "interrupted" })}
          onDeleted={onDeleted}
          onFork={noFork}
        />,
      );
      expect(container.querySelector('[data-testid="replay-delete-refused"]')).toBeNull();
    });

    it("says the simulator's refusal, and stays", async () => {
      const { container, onDeleted } = shown(
        "finished",
        Response.json({ error: "the store is read-only" }, { status: 500 }),
      );

      await confirmed(container);

      expect(onDeleted).not.toHaveBeenCalled();
      expect(said(container, "replay-delete-refused")).toContain("the store is read-only");
    });
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
          onDeleted={stays}
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
        onDeleted={stays}
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
        onDeleted={stays}
        onFork={noFork}
      />,
    );
    expect(said(rendered.container, "replay-failed")).toBe("This run failed.");
    rendered.unmount();

    rendered = render(
      <ReplayHeader
        name={null}
        position={position()}
        onDeleted={stays}
        failure="ignored"
        onFork={noFork}
      />,
    );
    expect(rendered.container.querySelector('[data-testid="replay-failed"]')).toBeNull();
  });

  describe("a fork from the moment shown", () => {
    function shown(onFork: () => void) {
      rendered = render(
        <ReplayHeader name={null} position={position()} onDeleted={stays} onFork={onFork} />,
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
          onDeleted={stays}
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
        onDeleted={stays}
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
        onDeleted={stays}
        forking
        forkRefused="no room"
        onFork={noFork}
      />,
    );
    const { container } = rendered;

    expect(said(container, "replay-fork-refused")).toBe("This run could not be forked: no room.");
    const refused = container.querySelector('[data-testid="replay-fork-refused"]');
    expect(refused?.getAttribute("role")).toBe("alert");
    expect(refused?.className).toContain("ds-notice-problem");
    const button = container.querySelector<HTMLButtonElement>('[data-testid="replay-fork"]');
    expect(button?.disabled).toBe(true);
    expect(button?.textContent).toBe("Forking…");
  });

  it("says what a fork came from, and links to it", () => {
    rendered = render(
      <ReplayHeader
        name={null}
        position={position({ fork: FORK, parent_kept: true })}
        onDeleted={stays}
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
        onDeleted={stays}
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
