// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { ScenarioSummary } from "../scenarios";
import { button, click, enter, type Rendered, render } from "../testing/render";
import { replayAddress, viewerAddress } from "./paths";
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
    damaged: false,
    ...more,
  };
}

type Asked = { url: string; method: string | undefined };
type Answer = { status: number; body: unknown };

/** The simulator, stood in for: every request is kept, and answered by
 * `answers` (by its method and address), else by `fallback`; */
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
      const answer = answers[`${init?.method ?? "GET"} ${url}`] ?? fallback;
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

  function shown(runs: StoredRun[], newRun = false) {
    const onClose = vi.fn();
    const onChanged = vi.fn();
    const navigate = vi.fn();
    const rendered = render(
      <RunsDialog
        scenario={SCENARIO}
        runs={runs}
        newRun={newRun}
        navigate={navigate}
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
    return { container: rendered.container, rows, field, navigate, onClose, onChanged };
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

  it("lists each run in words, and follows one computing in its replay", () => {
    const playing = run({
      epoch: 2,
      seed: 2,
      status: "running",
      frontier_s: 41 * DAY_S,
      progress: 41 / 120,
      layout: "default~heater:-1:0.5",
    });
    const replaced = run({ epoch: 1, seed: null, status: "running", progress: 0.5 });
    const { rows } = shown([
      playing,
      replaced,
      run({ epoch: 0, size_bytes: 400 * 1024, created_at: null }),
    ]);
    const texts = rows().map((row) => row.textContent);

    expect(texts[0]).toContain("Seed 2");
    expect(texts[0]).toContain("epoch 2 · Oct 28 · 24.0 MB");
    expect(texts[0]).toContain("Running");
    expect(texts[0]).toContain("41 of 120 days");
    expect(texts[1]).toContain("The scenario's seed");
    expect(texts[2]).toContain("epoch 0 · 400 kB");
    expect(texts[2]).toContain("Finished");
    // A finished one has no newest day to follow.
    expect(follows().map((a) => a.getAttribute("href"))).toEqual([
      replayAddress(RUN_ID, 2, true),
      replayAddress(RUN_ID, 1, true),
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

  describe("for a worker", () => {
    const RUNS_URL = "/api/scenarios/reference_greenhouse/runs";
    const STARTED = run({ epoch: 4, status: "queued", frontier_s: 0, progress: 0 });

    it("asks for it at the seed and the pace entered, and goes to its replay at the newest day", async () => {
      const asked = simulator({
        [`POST ${RUNS_URL}?seed=75&seconds_per_day=4`]: { status: 200, body: STARTED },
      });
      const { container, field, navigate } = shown([], true);

      enter(field("Seed"), "7x5");
      enter(field("Seconds per simulated day"), "4");
      click(button(container, "Start run"));

      await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
      expect(navigate).toHaveBeenCalledWith(replayAddress(RUN_ID, 4, true));
      // Only that: no playback is asked after, or replaced.
      expect(asked).toEqual([{ url: `${RUNS_URL}?seed=75&seconds_per_day=4`, method: "POST" }]);
    });

    it("leaves out a seed and a pace not entered: the scenario's own, as fast as it computes", async () => {
      const asked = simulator({ [`POST ${RUNS_URL}?`]: { status: 200, body: STARTED } });
      const { container, field, navigate } = shown([], true);

      enter(field("Seconds per simulated day"), "");
      click(button(container, "Start run"));

      await vi.waitFor(() => expect(navigate).toHaveBeenCalled());
      expect(asked.map((each) => each.url)).toEqual([`${RUNS_URL}?`]);
    });

    it("starts one run for two presses while the first is answered", async () => {
      let answer: (response: Response) => void = () => undefined;
      const fetchFn = vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            answer = resolve;
          }),
      );
      vi.stubGlobal("fetch", fetchFn);
      const { container, navigate } = shown([], true);

      click(button(container, "Start run"));
      click(button(container, "Start run"));
      expect(fetchFn).toHaveBeenCalledTimes(1);

      answer(new Response(JSON.stringify(STARTED)));
      await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
    });

    it("says why when it is refused, stays on the page, and can be asked again", async () => {
      const asked = simulator(
        {},
        { status: 400, body: { error: "a day takes some time to play" } },
      );
      const { container, navigate } = shown([], true);

      click(button(container, "Start run"));

      await vi.waitFor(() =>
        expect(container.querySelector('[role="alert"]')?.textContent).toContain(
          "a day takes some time to play",
        ),
      );
      expect(navigate).not.toHaveBeenCalled();
      await vi.waitFor(() =>
        expect((button(container, "Start run") as HTMLButtonElement).disabled).toBe(false),
      );
      click(button(container, "Start run"));
      await vi.waitFor(() => expect(asked).toHaveLength(2));
    });

    it("says when the answer is not a run", async () => {
      simulator({}, { status: 200, body: { not: "a run" } });
      const { container, navigate } = shown([], true);

      click(button(container, "Start run"));

      await vi.waitFor(() =>
        expect(container.querySelector('[role="alert"]')?.textContent).toContain("not a run"),
      );
      expect(navigate).not.toHaveBeenCalled();
    });
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
        body: { error: "run reference_greenhouse-climate-abc, epoch 0 is being computed" },
      },
    );
    const { container, onChanged } = shown([run({ status: "running" })]);

    click(button(container, "Delete the run with seed 1, epoch 0"));
    click(button(container, "Delete the run with seed 1, epoch 0"));

    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());
    // Which, as the row says it, and what to do with the button beside it.
    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      "The run with seed 1, epoch 0 is still being computed: stop it, then delete it.",
    );
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("offers to stop a run computing or waiting and to resume one interrupted, and nothing else", () => {
    const { rows } = shown([
      run({ epoch: 3, status: "running" }),
      run({ epoch: 2, status: "queued" }),
      run({ epoch: 1, status: "interrupted" }),
      run({ epoch: 0 }),
      run({ epoch: 4, status: "failed" }),
    ]);
    const words = rows().map((row) =>
      [...row.querySelectorAll("button")]
        .map((each) => each.textContent)
        .filter((each) => each === "Stop" || each === "Resume"),
    );

    expect(words).toEqual([["Stop"], ["Stop"], ["Resume"], [], []]);
  });

  it("calls a run with files missing damaged: no way in, and still a way to delete it", () => {
    const { rows, container } = shown([
      run({ epoch: 1, status: "finished", damaged: true }),
      run({ epoch: 0, status: "interrupted", damaged: true }),
    ]);
    const [finished, interrupted] = rows();

    expect(finished?.querySelector(".landing-status")?.textContent).toContain("Damaged");
    expect(finished?.textContent).toContain("cannot be read whole");
    expect(finished?.textContent).not.toContain("Finished");
    expect(interrupted?.textContent).not.toContain("Interrupted");
    expect(container.querySelector('a[aria-label^="Replay"]')).toBeNull();
    expect(follows()).toHaveLength(0);
    expect(container.querySelector('button[aria-label^="Resume"]')).toBeNull();
    expect(button(container, "Delete the run with seed 1, epoch 1")).toBeDefined();
  });

  it("can still stop a damaged run a worker is computing", () => {
    const { container } = shown([run({ status: "running", damaged: true })]);

    expect(button(container, "Stop the run with seed 1, epoch 0")).toBeDefined();
    expect(follows()).toHaveLength(0);
  });

  it("says what a fork came from, in its row; a run that is no fork says nothing of it", () => {
    const { rows } = shown([
      run({
        epoch: 3,
        fork: {
          run_id: "reference_greenhouse-climate-abc",
          epoch: 2,
          at_s: DAY_S + 3600,
          start_s: DAY_S,
          digest: null,
          checkpoint_sha256: null,
          inherited: 0,
          layout: null,
        },
      }),
      run({ epoch: 2 }),
    ]);

    expect(rows()[0]?.textContent).toContain(
      "epoch 3 · forked from epoch 2 at Day 2, 01:00 · Oct 28",
    );
    expect(rows()[1]?.textContent).not.toContain("forked");
  });

  it("stops a run through the epoch's route, and asks for the runs again", async () => {
    const asked = simulator({
      [`POST /api/runs/${RUN_ID}/epochs/3/stop`]: {
        status: 200,
        body: run({ epoch: 3, status: "interrupted" }),
      },
    });
    const { container, onChanged } = shown([run({ epoch: 3, status: "running" })]);

    click(button(container, "Stop the run with seed 1, epoch 3"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(asked).toEqual([{ url: `/api/runs/${RUN_ID}/epochs/3/stop`, method: "POST" }]);
  });

  it("resumes a run as fast as it computes, through the epoch's route", async () => {
    const asked = simulator({
      [`POST /api/runs/${RUN_ID}/epochs/3/resume`]: {
        status: 200,
        body: run({ epoch: 3, status: "queued" }),
      },
    });
    const { container, onChanged } = shown([run({ epoch: 3, status: "interrupted" })]);

    click(button(container, "Resume the run with seed 1, epoch 3"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(asked).toEqual([{ url: `/api/runs/${RUN_ID}/epochs/3/resume`, method: "POST" }]);
  });

  it("asks once for two presses while the first is answered", async () => {
    let answer: (response: Response) => void = () => undefined;
    const fetchFn = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          answer = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchFn);
    const { container, onChanged } = shown([run({ status: "running" })]);

    click(button(container, "Stop the run with seed 1, epoch 0"));
    click(button(container, "Stop the run with seed 1, epoch 0"));
    expect(fetchFn).toHaveBeenCalledTimes(1);

    answer(new Response(JSON.stringify(run({ status: "interrupted" }))));
    await vi.waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });

  it("says in words why a run has no worker to stop, with no identifier", async () => {
    simulator(
      {},
      { status: 404, body: { error: `epoch 0 of run ${RUN_ID} is neither waiting nor executed` } },
    );
    const { container, onChanged } = shown([run({ status: "running" })]);

    click(button(container, "Stop the run with seed 1, epoch 0"));

    await vi.waitFor(() =>
      expect(container.querySelector('[role="alert"]')?.textContent).toContain(
        "No worker of this simulator has this run.",
      ),
    );
    expect(container.textContent).not.toContain(RUN_ID);
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("says why a run does not resume, about this run and not its identifier", async () => {
    simulator(
      {},
      {
        status: 409,
        body: {
          error: `epoch 0 of ${RUN_ID} keeps no checkpoint at its frontier, from which to carry it on`,
        },
      },
    );
    const { container } = shown([run({ status: "interrupted" })]);

    click(button(container, "Resume the run with seed 1, epoch 0"));

    await vi.waitFor(() =>
      expect(container.querySelector('[role="alert"]')?.textContent).toBe(
        "this run keeps no checkpoint at its frontier, from which to carry it on",
      ),
    );
  });

  it("drops a problem once the run has moved on", async () => {
    simulator({}, { status: 404, body: { error: "gone" } });
    const { container } = shown([run({ status: "running" })]);
    click(button(container, "Stop the run with seed 1, epoch 0"));
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());

    drawn?.rerender(
      <RunsDialog
        scenario={SCENARIO}
        runs={[run({ status: "interrupted" })]}
        navigate={vi.fn()}
        onClose={vi.fn()}
        onChanged={vi.fn()}
      />,
    );

    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(button(container, "Resume the run with seed 1, epoch 0")).toBeDefined();
  });

  it("drops what a refused deletion said once the run has been stopped as it asked", async () => {
    simulator({
      [`POST /api/runs/${RUN_ID}/epochs/0/delete`]: { status: 409, body: { error: "computing" } },
      [`POST /api/runs/${RUN_ID}/epochs/0/stop`]: {
        status: 200,
        body: run({ status: "interrupted" }),
      },
    });
    const { container, onChanged } = shown([run({ status: "running" })]);
    click(button(container, "Delete the run with seed 1, epoch 0"));
    click(button(container, "Delete the run with seed 1, epoch 0"));
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());

    click(button(container, "Stop the run with seed 1, epoch 0"));

    await vi.waitFor(() => expect(onChanged).toHaveBeenCalled());
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).toBeNull());
  });

  it("is closed by its button, and when the browser closes it", () => {
    const { container, onClose } = shown([]);

    click(button(container, "Close"));
    act(() => container.querySelector("dialog")?.dispatchEvent(new Event("close")));

    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
