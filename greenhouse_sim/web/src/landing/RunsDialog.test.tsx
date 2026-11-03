// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { ScenarioSummary } from "../scenarios";
import { button, click, enter, type Rendered, render } from "../testing/render";
import { followAddress } from "./follow";
import { viewerAddress } from "./paths";
import { runKey } from "./playing";
import { RunsDialog } from "./RunsDialog";
import type { StoredRun } from "./storedRuns";

const SCENARIO: ScenarioSummary = {
  id: "reference_greenhouse",
  name: "Reference greenhouse",
  description: "organ-level tomato crop",
  plants: 32,
  duration_days: 120,
  layouts: ["default"],
};
const RUN_ID = "reference_greenhouse-climate-abc";
const PLAYBACK_URL = "/api/scenarios/reference_greenhouse/playback";

function run(more: Partial<StoredRun>): StoredRun {
  return {
    run_id: RUN_ID,
    epoch: 0,
    scenario_id: "reference_greenhouse",
    seed: 1,
    layout: "default",
    status: "finished",
    frontier_s: 120 * DAY_S,
    duration_s: 120 * DAY_S,
    progress: 1,
    created_at: "2026-10-28T09:30:00Z",
    size_bytes: 24 * 1024 * 1024,
    start_s: 0,
    fork: null,
    ...more,
  };
}

/** A scenario's playback, as the simulator answers for it. */
function playback(runId: string, epoch: number, layout = "default") {
  return {
    scenario_id: "reference_greenhouse",
    run_id: runId,
    layout,
    epoch,
    greenhouse_id: "reference_greenhouse",
    started_at: "2026-02-28T23:00:00Z",
    simulated_now: "2026-03-02T11:00:30Z",
    time_s: 0,
    day: 0,
    playing: true,
    seconds_per_day: 10,
    worked_out_s: 86_400,
    every_s: 300,
    targets: [],
    commands: [],
    crop: [],
  };
}

type Asked = { url: string; method: string | undefined };
type Answer = { status: number; body: unknown };

/** The simulator, stood in for: every request is kept, and answered by
 * `answers` (by its method and address), else by `fallback`; a playback not
 * started is not found. */
function simulator(
  answers: Record<string, Answer> = {},
  fallback: Answer = { status: 200, body: {} },
): Asked[] {
  const asked: Asked[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      asked.push({ url, method: init?.method });
      const answer =
        answers[`${init?.method ?? "GET"} ${url}`] ??
        (url === PLAYBACK_URL ? { status: 404, body: { error: "no playback" } } : fallback);
      return new Response(JSON.stringify(answer.body), { status: answer.status });
    }),
  );
  return asked;
}

describe("the runs of a scenario, in a dialog", () => {
  let drawn: Rendered | undefined;
  afterEach(() => {
    drawn?.unmount();
    vi.unstubAllGlobals();
  });

  function shown(runs: StoredRun[], newRun = false, followed: ReadonlySet<string> = new Set()) {
    const onClose = vi.fn();
    const onChanged = vi.fn();
    const rendered = render(
      <RunsDialog
        scenario={SCENARIO}
        runs={runs}
        followed={followed}
        newRun={newRun}
        onClose={onClose}
        onChanged={onChanged}
      />,
    );
    drawn = rendered;
    const rows = () => [...rendered.container.querySelectorAll(".landing-run")];
    const field = (name: string) => {
      const found = [...rendered.container.querySelectorAll("label")].find((each) =>
        each.textContent?.startsWith(name),
      );
      const input = found?.querySelector("input");
      if (input === null || input === undefined) {
        throw new Error(`no field ${name}`);
      }
      return input;
    };
    return { container: rendered.container, rows, field, onClose, onChanged };
  }

  const follows = () =>
    [...document.querySelectorAll("a")].filter((a) => a.textContent === "Follow");

  it("opens as a dialog that names the scenario, and links to it in the viewer", () => {
    const { container } = shown([]);
    const dialog = container.querySelector("dialog");

    expect(dialog?.hasAttribute("open")).toBe(true);
    expect(dialog?.getAttribute("aria-labelledby")).toBe(container.querySelector("h2")?.id);
    expect(container.querySelector("h2")?.textContent).toBe("Reference greenhouse");
    expect(container.querySelector(`a[href="${viewerAddress(SCENARIO.id)}"]`)).not.toBeNull();
  });

  it("lists each run in words, and offers to follow only the one its playback is playing", () => {
    const playing = run({
      epoch: 2,
      seed: 2,
      status: "running",
      frontier_s: 41 * DAY_S,
      progress: 41 / 120,
      layout: "default~heater:-1:0.5",
    });
    const replaced = run({ epoch: 1, seed: null, status: "running", progress: 0.5 });
    const { rows } = shown(
      [playing, replaced, run({ epoch: 0, size_bytes: 400 * 1024, created_at: null })],
      false,
      new Set([runKey(playing)]),
    );
    const texts = rows().map((row) => row.textContent);

    expect(texts[0]).toContain("Seed 2");
    expect(texts[0]).toContain("epoch 2 · Oct 28 · 24.0 MB");
    expect(texts[0]).toContain("Running");
    expect(texts[0]).toContain("41 of 120 days");
    expect(texts[1]).toContain("The scenario's seed");
    expect(texts[2]).toContain("epoch 0 · 400 kB");
    expect(texts[2]).toContain("Finished");
    // A run computing is followed only if the playback is on that epoch: the
    // second, which another run replaced, is not, and nor is a finished one.
    expect(follows().map((a) => a.getAttribute("href"))).toEqual([
      followAddress(SCENARIO.id, "default~heater:-1:0.5"),
    ]);
  });

  it("says so when there is no run yet, and offers the form for one", () => {
    const { container, field } = shown([]);
    expect(container.textContent).toContain("No runs of this scenario yet.");
    expect(container.querySelector("form")).toBeNull();

    click(button(container, "New run"));

    expect(field("Seed").placeholder).toBe("The scenario's own");
    expect(field("Seconds per simulated day").value).toBe("10");
  });

  it("starts a run at the seed and the pace entered, and says where to follow it", async () => {
    const asked = simulator({
      "POST /api/scenarios/reference_greenhouse/playback/start?seconds_per_day=4&seed=75": {
        status: 200,
        body: playback("reference_greenhouse-climate-seeded", 0),
      },
    });
    const { container, field, onChanged } = shown([], true);

    enter(field("Seed"), "7x5");
    enter(field("Seconds per simulated day"), "4");
    expect(field("Seed").value).toBe("75");
    click(button(container, "Start run"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(asked).toEqual([
      { url: PLAYBACK_URL, method: undefined },
      {
        url: "/api/scenarios/reference_greenhouse/playback/start?seconds_per_day=4&seed=75",
        method: "POST",
      },
    ]);
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      "Run started, as epoch 0.",
    );
    expect(container.querySelector(`a[href="${followAddress(SCENARIO.id)}"]`)?.textContent).toBe(
      "Follow it in the viewer",
    );
  });

  it("asks for the scenario's own seed when none is entered, not for the playback's", async () => {
    const asked = simulator({
      "POST /api/scenarios/reference_greenhouse/playback/start?seconds_per_day=10&seed=default": {
        status: 200,
        body: playback("reference_greenhouse-climate-own", 0),
      },
    });
    const { container, onChanged } = shown([], true);

    click(button(container, "Start run"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(asked.at(-1)?.url).toBe(
      "/api/scenarios/reference_greenhouse/playback/start?seconds_per_day=10&seed=default",
    );
  });

  it("does not call a run started that the playback was already playing, and offers a new epoch", async () => {
    const playing = playback(RUN_ID, 3);
    const asked = simulator({
      [`GET ${PLAYBACK_URL}`]: { status: 200, body: playing },
      "POST /api/scenarios/reference_greenhouse/playback/start?seconds_per_day=10&seed=1": {
        status: 200,
        body: playing,
      },
      "POST /api/scenarios/reference_greenhouse/playback/restart": {
        status: 200,
        body: playback(RUN_ID, 4),
      },
    });
    const { container, field, onChanged } = shown([run({ epoch: 3 })], true);

    enter(field("Seed"), "1");
    click(button(container, "Start run"));

    await vi.waitFor(() =>
      expect(container.querySelector('[role="status"]')?.textContent).toContain(
        "That run is the one playing already, as epoch 3",
      ),
    );
    expect(container.querySelector('[role="status"]')?.textContent).not.toContain("Run started");

    click(button(container, "Start it again as a new epoch"));

    await vi.waitFor(() =>
      expect(container.querySelector('[role="status"]')?.textContent).toContain(
        "Run started, as epoch 4.",
      ),
    );
    expect(asked.at(-1)).toEqual({
      url: "/api/scenarios/reference_greenhouse/playback/restart",
      method: "POST",
    });
    expect(onChanged).toHaveBeenCalledTimes(2);
  });

  it("says why when the simulator refuses a run, and does not say it started", async () => {
    simulator({}, { status: 404, body: { error: "there is no scenario 'reference_greenhouse'" } });
    const { container, onChanged } = shown([], true);

    click(button(container, "Start run"));

    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "there is no scenario",
    );
    expect(container.querySelector('[role="status"]')).toBeNull();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("removes a run only once it is confirmed, and not when it is kept", async () => {
    const asked = simulator();
    const { container, onChanged } = shown([run({ epoch: 3, seed: 5 })]);

    click(button(container, "Delete the run with seed 5, epoch 3"));
    click(button(container, "Keep it"));
    expect(asked).toEqual([]);
    expect(button(container, "Delete the run with seed 5, epoch 3")).toBeDefined();

    click(button(container, "Delete the run with seed 5, epoch 3"));
    click(button(container, "Delete the run with seed 5, epoch 3"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(asked).toEqual([{ url: `/api/runs/${RUN_ID}/epochs/3/delete`, method: "POST" }]);
  });

  it("says why when a run is not removed", async () => {
    simulator(
      {},
      {
        status: 409,
        body: { error: "run x, epoch 0 is being computed: wait for it, or stop it" },
      },
    );
    const { container, onChanged } = shown([run({ status: "running" })]);

    click(button(container, "Delete the run with seed 1, epoch 0"));
    click(button(container, "Delete the run with seed 1, epoch 0"));

    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("being computed");
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("is closed by its button, and when the browser closes it", () => {
    const { container, onClose } = shown([]);

    click(button(container, "Close"));
    act(() => container.querySelector("dialog")?.dispatchEvent(new Event("close")));

    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
