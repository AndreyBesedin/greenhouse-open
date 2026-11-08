// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { ScenarioSummary } from "../scenarios";
import { type Rendered, render } from "../testing/render";
import { Landing } from "./Landing";
import { REPOSITORY_URL, replayAddress } from "./paths";
import type { Room } from "./room";
import { RUNS_ASKED_EVERY_MS, type StoredRun } from "./storedRuns";

// What the simulator sends of a scenario besides its name: how it grows its
// crop, its daily commands, openings and weathers, its opening day and heater.
const SENT = {
  crop_model: "simple",
  daily: [],
  openings: [],
  weathers: ["default"],
  opening_day: null,
  thermostat: null,
};
const SCENARIOS: ScenarioSummary[] = [
  {
    ...SENT,
    id: "reference_greenhouse",
    name: "Reference greenhouse",
    description: "organ-level tomato crop",
    plants: 32,
    duration_days: 120,
    layouts: ["default"],
  },
  {
    ...SENT,
    id: "tomgro_house",
    name: "TOMGRO house",
    description: "crop grown by area",
    plants: 0,
    duration_days: 120,
    layouts: ["default"],
  },
];

const ROOM: Room = {
  workers_busy: 1,
  workers_limit: 2,
  runs_waiting: 0,
  runs_waiting_limit: 200,
  disk_free_bytes: 45_200_000_000,
  disk_free_limit_bytes: 2_000_000_000,
  refusal: null,
};

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
    size_bytes: 1024,
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

/** The simulator, stood in for: each address answers what it is given, or
 * fails if it is given an error. */
function simulator(answers: Record<string, unknown>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const answer = answers[String(input)];
      if (answer instanceof Error) {
        throw answer;
      }
      return new Response(JSON.stringify(answer), { status: answer === undefined ? 404 : 200 });
    }),
  );
}

describe("the page where a person decides what to do", () => {
  let page: Rendered | undefined;
  afterEach(() => {
    page?.unmount();
    vi.unstubAllGlobals();
  });

  async function shown(
    answers: Record<string, unknown>,
    waitFor: string,
  ): Promise<{ container: HTMLElement; navigate: ReturnType<typeof vi.fn> }> {
    simulator(answers);
    const navigate = vi.fn();
    page = render(<Landing navigate={navigate} />);
    const { container } = page;
    await vi.waitFor(() => expect(container.textContent).toContain(waitFor));
    return { container, navigate };
  }

  const link = (within: ParentNode, name: string) =>
    [...within.querySelectorAll("a")].find((each) => each.textContent?.trim() === name);

  it("links to the project's code in a page of its own, and to the builder", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [] },
      "No run has been kept yet",
    );

    const contribute = link(container, "Contribute");
    expect(contribute?.getAttribute("href")).toBe(REPOSITORY_URL);
    expect(contribute?.getAttribute("target")).toBe("_blank");
    expect(contribute?.getAttribute("rel")).toContain("noopener");
    // The mark is decoration: the link keeps its name from its text.
    const mark = contribute?.querySelector("svg");
    expect(mark?.getAttribute("aria-hidden")).toBe("true");
    expect(contribute?.textContent).toBe("Contribute");
    expect(link(container, "Open the builder")?.getAttribute("href")).toBe("/builder");
  });

  const draft = (id: string, saved: string) => ({
    draft_id: id,
    name: `House ${id}`,
    revision: 2,
    saved_at: saved,
  });

  it("lists the latest drafts saved in the card to build one, each opening in the builder", async () => {
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [],
        "/api/drafts": [
          draft("oldest", "2026-09-01T12:00:00Z"),
          draft("latest", "2026-11-03T12:00:00Z"),
          draft("older", "2026-10-01T12:00:00Z"),
          draft("late", "2026-11-01T12:00:00Z"),
        ],
      },
      "Saved drafts",
    );

    const list = container.querySelector('#landing-build ~ nav[aria-label="Saved drafts"]');
    expect(
      [...(list?.querySelectorAll("a") ?? [])].map((each) => [
        each.textContent,
        each.getAttribute("href"),
      ]),
    ).toEqual([
      ["House latest", "/builder#draft=latest"],
      ["House late", "/builder#draft=late"],
      ["House older", "/builder#draft=older"],
    ]);
    expect(list?.textContent).toContain("Saved drafts, the latest 3 of 4");
    expect(list?.querySelector("span")?.textContent).toBe("revision 2 · saved Nov 3");
  });

  it("lists no drafts when none is saved, or the simulator keeps none", async () => {
    for (const drafts of [{ "/api/drafts": [] }, {}]) {
      const { container } = await shown(
        { "/api/scenarios": SCENARIOS, "/api/runs": [], ...drafts },
        "No run has been kept yet",
      );
      await vi.waitFor(() =>
        expect(vi.mocked(fetch).mock.calls.map(([url]) => String(url))).toContain("/api/drafts"),
      );
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(container.textContent).not.toContain("Saved drafts");
      page?.unmount();
      page = undefined;
    }
  });

  it("says how many runs are kept and what their objects hold, above the list, once", async () => {
    const MB = 1000 * 1000;
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [run({ size_bytes: 8 * MB }), run({ epoch: 1, size_bytes: 4 * MB })],
      },
      "2 runs kept",
    );

    const kept = container.querySelector('[data-testid="landing-kept"]');
    expect(kept?.textContent).toContain("2 runs kept, 12.0 MB");
    expect(kept?.getAttribute("title")).toContain("not of the disk");
    expect(kept?.textContent).toContain("not of the disk");
  });

  it("says the room for runs above the list, each figure beside its limit, with none kept yet", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [], "/api/room": ROOM },
      "Workers",
    );

    const room = container.querySelector('[data-testid="landing-room"]');
    expect([...(room?.querySelectorAll("dt") ?? [])].map((each) => each.textContent)).toEqual([
      "Workers",
      "Waiting",
      "Free disk",
    ]);
    expect(room?.textContent).toContain("1 of 2 busy");
    expect(room?.textContent).toContain("none, of 200 runs that may wait");
    expect(room?.textContent).toContain("45.2 GB, and a run begins only with 2.0 GB");
    expect(container.querySelector(".landing-room-refusal")).toBeNull();
    expect(container.textContent).toContain("No run has been kept yet");
  });

  it("says, in the simulator's words, the refusal a run asked for now would be given", async () => {
    const refusal =
      "the disk of the run store has 1.2 GB free, and a run begins only with 2.0 GB free: free some space, or lower that limit";
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [],
        "/api/room": { ...ROOM, disk_free_bytes: 1_200_000_000, refusal },
      },
      "Workers",
    );

    expect(container.querySelector(".landing-room-refusal")?.textContent).toBe(
      `A run asked for now is refused: ${refusal}.`,
    );
  });

  it("says why the room for runs cannot be read, and lists the runs all the same", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [run({})] },
      "The room for runs cannot be read",
    );

    expect(container.querySelector(".landing-room")?.textContent).toBe(
      "The room for runs cannot be read: the simulator API answered 404.",
    );
    expect(container.querySelectorAll(".landing-run")).toHaveLength(1);
  });

  it("says on each row what the run used, and why one failed", async () => {
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [
          run({
            status: "failed",
            past_limit: true,
            size_bytes: 21_000_000,
            days_computed: 41,
            cpu_s: 1357,
            peak_memory_bytes: 328_000_000,
            wall_s: 2640,
            reason: "it kept 21.0 MB, past the limit of 20.0 MB on what one run may keep",
          }),
          run({ epoch: 1 }),
        ],
        "/api/room": ROOM,
      },
      "Peak memory",
    );

    const [failed, finished] = [...container.querySelectorAll(".landing-run")];
    expect(failed?.querySelector(".landing-run-usage")?.textContent).toBe(
      "Kept21.0 MBComputed41 daysCPU22 min 37 sPeak memory328.0 MBWall time44 min",
    );
    expect(failed?.querySelector(".landing-run-reason")?.textContent).toBe(
      "This run failed: it kept 21.0 MB, past the limit of 20.0 MB on what one run may keep.",
    );
    // Ended by a limit, it can be carried on once the limit is raised.
    expect(failed?.querySelector('[aria-label^="Resume"]')).not.toBeNull();
    expect(finished?.querySelector(".landing-run-reason")).toBeNull();
    expect(finished?.querySelector(".landing-run-usage")?.textContent).toContain("CPUnot measured");
  });

  it("says nothing of volume when no run is kept, only that none is", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [] },
      "No run has been kept yet",
    );

    expect(container.querySelector('[data-testid="landing-kept"]')).toBeNull();
    expect(container.textContent).not.toContain("runs kept");
  });

  it("opens the runs of the scenario that is chosen in a dialog, and the builder in a page", async () => {
    const { container, navigate } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [run({})] },
      "Reference greenhouse",
    );
    const input = container.querySelector("input");
    act(() => input?.click());
    const options = () => [...container.querySelectorAll('[role="option"]')];
    const pointOn = (option: Element | undefined) =>
      act(() => {
        option?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      });

    expect(options()[0]?.textContent).toContain("1 run");
    expect(options()[1]?.textContent).toContain("no runs");
    pointOn(options()[1]);

    expect(container.querySelector("dialog h2")?.textContent).toBe("TOMGRO house");
    expect(container.querySelector("dialog")?.textContent).toContain(
      "No runs of this scenario yet.",
    );
    expect(navigate).not.toHaveBeenCalled();
    act(() =>
      container
        .querySelector<HTMLButtonElement>(".landing-dialog-actions button:last-child")
        ?.click(),
    );
    expect(container.querySelector("dialog")).toBeNull();

    act(() => input?.click());
    pointOn(options().at(-1));
    expect(navigate).toHaveBeenLastCalledWith("/builder");
  });

  it("shows only the chosen scenario's runs in its dialog, and asks for them again once one is removed", async () => {
    const mine = run({ epoch: 4, seed: 9 });
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [mine, run({ scenario_id: "tomgro_house", epoch: 0, seed: 3 })],
        "/api/runs/reference_greenhouse-climate-abc/epochs/4/delete": { deleted: "x" },
      },
      "epoch 4",
    );
    const input = container.querySelector("input");
    act(() => input?.click());
    act(() => {
      container
        .querySelector('[role="option"]')
        ?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    });

    const inDialog = () => [...container.querySelectorAll("dialog .landing-run")];
    expect(inDialog().map((row) => row.textContent)).toEqual([expect.stringContaining("Seed 9")]);
    const named = (name: string) =>
      [...container.querySelectorAll<HTMLButtonElement>("dialog button")].find(
        (each) => (each.getAttribute("aria-label") ?? each.textContent?.trim()) === name,
      );
    act(() => (named("Delete the run with seed 9, epoch 4") as HTMLButtonElement).click());
    act(() => (named("Delete the run with seed 9, epoch 4") as HTMLButtonElement).click());

    await vi.waitFor(() =>
      expect(
        vi.mocked(fetch).mock.calls.filter(([url]) => String(url) === "/api/runs"),
      ).toHaveLength(2),
    );
  });

  it("asks for the runs again after each removal, however many are in flight together", async () => {
    const first = run({ epoch: 0, seed: 1 });
    const second = run({ epoch: 1, seed: 2 });
    // The removals answer only when released, so that both are under way
    // before either is done.
    const release: Array<() => void> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/delete")) {
          await new Promise<void>((resolve) => release.push(resolve));
          return new Response(JSON.stringify({ deleted: url }));
        }
        const bodies: Record<string, unknown> = {
          "/api/scenarios": SCENARIOS,
          "/api/runs": [first, second],
        };
        return new Response(JSON.stringify(bodies[url]), { status: url in bodies ? 200 : 404 });
      }),
    );
    const navigate = vi.fn();
    page = render(<Landing navigate={navigate} />);
    const { container } = page;
    await vi.waitFor(() => expect(container.textContent).toContain("epoch 1"));
    const input = container.querySelector("input");
    act(() => input?.click());
    act(() => {
      container
        .querySelector('[role="option"]')
        ?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    });
    const named = (name: string) =>
      [...container.querySelectorAll<HTMLButtonElement>("dialog button")].find(
        (each) => (each.getAttribute("aria-label") ?? each.textContent?.trim()) === name,
      );
    const asks = () =>
      vi.mocked(fetch).mock.calls.filter(([url]) => String(url) === "/api/runs").length;
    expect(asks()).toBe(1);

    for (const who of ["seed 1, epoch 0", "seed 2, epoch 1"]) {
      act(() => named(`Delete the run with ${who}`)?.click());
      act(() => named(`Delete the run with ${who}`)?.click());
    }
    expect(release).toHaveLength(2);

    act(() => release[0]?.());
    await vi.waitFor(() => expect(asks()).toBe(2));
    act(() => release[1]?.());
    await vi.waitFor(() => expect(asks()).toBe(3));
  });

  it("says so when the address asks for a scenario the simulator does not have", async () => {
    simulator({ "/api/scenarios": SCENARIOS, "/api/runs": [] });
    page = render(<Landing hash="#run=no_such" navigate={vi.fn()} />);
    const { container } = page;

    await vi.waitFor(() =>
      expect(container.querySelector('[role="alert"]')?.textContent).toContain("no_such"),
    );
    expect(container.querySelector("dialog")).toBeNull();
  });

  it("leaves the address that asked for a dialog once the dialog is closed", async () => {
    history.replaceState(null, "", "/#runs=tomgro_house");
    simulator({ "/api/scenarios": SCENARIOS, "/api/runs": [] });
    page = render(<Landing navigate={vi.fn()} />);
    const { container } = page;
    await vi.waitFor(() => expect(container.querySelector("dialog")).not.toBeNull());

    const close = [...container.querySelectorAll("dialog button")].find(
      (each) => each.textContent === "Close",
    ) as HTMLButtonElement;
    act(() => close.click());

    expect(container.querySelector("dialog")).toBeNull();
    expect(location.hash).toBe("");
    expect(location.pathname).toBe("/");
  });

  it("opens a scenario's form for a new run when the address asks for it", async () => {
    simulator({ "/api/scenarios": SCENARIOS, "/api/runs": [] });
    page = render(<Landing hash="#run=tomgro_house" navigate={vi.fn()} />);
    const { container } = page;

    await vi.waitFor(() =>
      expect(container.querySelector("dialog h2")?.textContent).toBe("TOMGRO house"),
    );
    expect(container.querySelector("dialog form")).not.toBeNull();
  });

  it("lists the latest runs in words, with one way to watch each", async () => {
    const running = run({
      epoch: 1,
      seed: 2,
      status: "running",
      paused: false,
      frontier_s: 41 * DAY_S,
      progress: 41 / 120,
    });
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [
          running,
          run({
            scenario_id: "tomgro_house",
            seed: null,
            status: "interrupted",
            paused: false,
            frontier_s: 63 * DAY_S,
          }),
          run({ epoch: 3, status: "failed", frontier_s: 5 * DAY_S, created_at: null }),
        ],
      },
      "Recent runs",
    );
    await vi.waitFor(() => expect(container.querySelectorAll(".landing-run")).toHaveLength(3));
    const rows = [...container.querySelectorAll(".landing-run")].map((row) => row.textContent);

    expect(rows[0]).toContain("Reference greenhouse");
    expect(rows[0]).toContain("seed 2 · epoch 1 · Oct 28");
    expect(rows[0]).toContain("Running");
    expect(rows[0]).toContain("41 of 120 days");
    expect(rows[1]).toContain("TOMGRO house");
    expect(rows[1]).toContain("the scenario's seed · epoch 0");
    expect(rows[1]).toContain("Interrupted");
    expect(rows[2]).toContain("Failed");
    expect(rows[2]).not.toContain("Oct");
    // One way to watch each (P22.2): its replay, following the newest day of the
    // one being computed.
    const watches = [...container.querySelectorAll(".landing-run")].map((row) =>
      [...row.querySelectorAll("a")]
        .filter((each) => each.textContent === "Replay" || each.textContent === "Follow")
        .map((each) => each.getAttribute("href")),
    );
    expect(watches).toEqual([
      [replayAddress(running.run_id, 1, true)],
      [replayAddress(running.run_id, 0)],
      [replayAddress(running.run_id, 3)],
    ]);
  });

  it("moves a run being computed on by itself, and stops asking once none is", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const answers = [
        [run({ status: "running", frontier_s: DAY_S, progress: 1 / 120 })],
        [run({ status: "running", frontier_s: 2 * DAY_S, progress: 2 / 120 })],
        [run({})],
      ];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          const body =
            url === "/api/scenarios"
              ? SCENARIOS
              : url === "/api/drafts"
                ? []
                : url === "/api/room"
                  ? ROOM
                  : (answers.shift() ?? [run({})]);
          return new Response(JSON.stringify(body));
        }),
      );
      page = render(<Landing navigate={vi.fn()} />);
      const { container } = page;
      const asked = () =>
        vi.mocked(fetch).mock.calls.filter(([url]) => String(url) === "/api/runs").length;

      await vi.waitFor(() => expect(container.textContent).toContain("1 of 120 days"));
      expect(container.textContent).toContain("Running");

      await act(() => vi.advanceTimersByTimeAsync(RUNS_ASKED_EVERY_MS));
      await vi.waitFor(() => expect(container.textContent).toContain("2 of 120 days"));

      await act(() => vi.advanceTimersByTimeAsync(RUNS_ASKED_EVERY_MS));
      await vi.waitFor(() => expect(container.textContent).toContain("Finished"));
      const whenDone = asked();
      expect(whenDone).toBe(3);

      await act(() => vi.advanceTimersByTimeAsync(3 * RUNS_ASKED_EVERY_MS));
      expect(asked()).toBe(whenDone);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops a run from the list and asks for the runs again", async () => {
    const running = run({ status: "running", frontier_s: DAY_S, progress: 1 / 120 });
    let stopped = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === `/api/runs/${running.run_id}/epochs/0/stop` && init?.method === "POST") {
          stopped = true;
          return new Response(JSON.stringify({ ...running, status: "interrupted" }));
        }
        const body =
          url === "/api/scenarios"
            ? SCENARIOS
            : url === "/api/runs"
              ? [stopped ? { ...running, status: "interrupted" } : running]
              : undefined;
        return new Response(JSON.stringify(body), { status: body === undefined ? 404 : 200 });
      }),
    );
    page = render(<Landing navigate={vi.fn()} />);
    const { container } = page;
    await vi.waitFor(() =>
      expect(container.querySelector('button[aria-label^="Stop"]')).not.toBeNull(),
    );

    act(() =>
      container
        .querySelector<HTMLButtonElement>(
          'button[aria-label="Stop the run of Reference greenhouse"]',
        )
        ?.click(),
    );

    await vi.waitFor(() => expect(container.textContent).toContain("Interrupted"));
    expect(
      container.querySelector('button[aria-label="Resume the run of Reference greenhouse"]'),
    ).not.toBeNull();
  });

  describe("deleting from the list of recent runs", () => {
    const DELETE = "Delete the run of Reference greenhouse with seed 9, epoch 4";
    const DELETE_URL = "/api/runs/reference_greenhouse-climate-abc/epochs/4/delete";

    /** The page with one run in its list, the deletion answered as `answer`. */
    async function listed(mine: StoredRun, answer: () => Response) {
      const asked: string[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          asked.push(url);
          if (url === DELETE_URL) {
            return answer();
          }
          if (url.endsWith("/stop")) {
            return new Response(JSON.stringify({ ...mine, stopping: true }));
          }
          const body = url === "/api/scenarios" ? SCENARIOS : [mine];
          return new Response(JSON.stringify(body));
        }),
      );
      page = render(<Landing navigate={vi.fn()} />);
      const { container } = page;
      await vi.waitFor(() => expect(container.querySelector(".landing-run")).not.toBeNull());
      const named = (name: string) =>
        [...container.querySelectorAll<HTMLButtonElement>(".landing-run button")].find(
          (each) => (each.getAttribute("aria-label") ?? each.textContent?.trim()) === name,
        );
      return { container, asked, named };
    }

    it("removes a run only once it is confirmed, and asks for the runs again", async () => {
      const { asked, named } = await listed(
        run({ epoch: 4, seed: 9 }),
        () => new Response(JSON.stringify({ deleted: "x" })),
      );

      act(() => named(DELETE)?.click());
      expect(asked).not.toContain(DELETE_URL);
      act(() => named(DELETE)?.click());

      await vi.waitFor(() => expect(asked).toContain(DELETE_URL));
      await vi.waitFor(() => expect(asked.filter((url) => url === "/api/runs")).toHaveLength(2));
    });

    it("puts the keyboard on the list's heading once the run has gone, not on the page", async () => {
      const { container, named } = await listed(
        run({ epoch: 4, seed: 9 }),
        () => new Response(JSON.stringify({ deleted: "x" })),
      );

      act(() => named(DELETE)?.click());
      act(() => named(DELETE)?.click());

      const heading = [...container.querySelectorAll("h3")].find(
        (each) => each.textContent === "Recent runs",
      );
      await vi.waitFor(() => expect(document.activeElement).toBe(heading));
    });

    it("keeps a run when asked to, with the keyboard back where it was", async () => {
      const { asked, named } = await listed(
        run({ epoch: 4, seed: 9 }),
        () => new Response(JSON.stringify({ deleted: "x" })),
      );

      act(() => named(DELETE)?.click());
      // Not on what cannot be undone.
      expect(document.activeElement).toBe(named("Keep it"));
      act(() => named("Keep it")?.click());

      expect(asked).not.toContain(DELETE_URL);
      expect(document.activeElement).toBe(named(DELETE));
    });

    /** The page with `mine` in its list, its deletion refused as being computed. */
    async function refused(mine: StoredRun) {
      const page = await listed(
        mine,
        () => new Response(JSON.stringify({ error: "being computed" }), { status: 409 }),
      );
      act(() => page.named(DELETE)?.click());
      act(() => page.named(DELETE)?.click());
      const alert = () => page.container.querySelector('.landing-run [role="alert"]');
      return { ...page, alert };
    }

    it("says on the row why a run is not removed, until it is over", async () => {
      const mine = run({ epoch: 4, seed: 9, status: "running" });
      const { named, asked, alert } = await refused(mine);

      await vi.waitFor(() =>
        expect(alert()?.textContent).toBe(
          "The run of Reference greenhouse with seed 9, epoch 4 is still being computed: stop it, then delete it.",
        ),
      );
      expect(document.activeElement).toBe(named(DELETE));

      // The list is asked for again while a run is computed, and it has finished.
      mine.status = "finished";
      await vi.waitFor(() => expect(alert()).toBeNull(), { timeout: RUNS_ASKED_EVERY_MS * 2 });
      expect(asked).toContain(DELETE_URL);
    });

    it.each([
      [
        "paused",
        { paused: true },
        "The run of Reference greenhouse with seed 9, epoch 4 is paused, not over: stop it, then delete it.",
      ],
      [
        "stopping",
        { stopping: true },
        "The run of Reference greenhouse with seed 9, epoch 4 is stopping: delete it once it reads Interrupted.",
      ],
      [
        "queued",
        { status: "queued" },
        "The run of Reference greenhouse with seed 9, epoch 4 is waiting for a worker: stop it, then delete it.",
      ],
    ] as const)("reads a refusal off the row, now it is %s", async (_, now, said) => {
      const mine = run({ epoch: 4, seed: 9, status: "running" });
      const { alert } = await refused(mine);
      await vi.waitFor(() => expect(alert()?.textContent).toContain("still being computed"));

      // The row's status has not moved on, or not to anything over: the words do.
      Object.assign(mine, now);

      await vi.waitFor(() => expect(alert()?.textContent).toBe(said), {
        timeout: RUNS_ASKED_EVERY_MS * 2,
      });
    });

    it("says a row that reads paused is paused as the deletion is refused", async () => {
      const { alert } = await refused(run({ epoch: 4, seed: 9, status: "running", paused: true }));

      await vi.waitFor(() =>
        expect(alert()?.textContent).toBe(
          "The run of Reference greenhouse with seed 9, epoch 4 is paused, not over: stop it, then delete it.",
        ),
      );
    });

    it("says a run over by its status is being written still, and asks for the runs again", async () => {
      const { alert, asked } = await refused(run({ epoch: 4, seed: 9, status: "interrupted" }));

      await vi.waitFor(() =>
        expect(alert()?.textContent).toBe(
          "The run of Reference greenhouse with seed 9, epoch 4 is still being written: try again.",
        ),
      );
      await vi.waitFor(() => expect(asked.filter((url) => url === "/api/runs")).toHaveLength(2));
    });

    it("does not say it again of a run computed again, once it has been over", async () => {
      const mine = run({ epoch: 4, seed: 9, status: "running" });
      const { alert } = await refused(mine);
      await vi.waitFor(() => expect(alert()).not.toBeNull());

      // Stopped, then resumed: each is read with the list, which is still asked
      // for as the next run below stays computed.
      const other = run({ run_id: "reference_greenhouse-climate-other", status: "running" });
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          const body = url === "/api/scenarios" ? SCENARIOS : [mine, other];
          return new Response(JSON.stringify(body));
        }),
      );
      mine.status = "interrupted";
      await vi.waitFor(() => expect(alert()).toBeNull(), { timeout: RUNS_ASKED_EVERY_MS * 2 });
      mine.status = "running";
      await vi.waitFor(
        () =>
          expect(page?.container.querySelector(".landing-run")?.textContent).toContain("Running"),
        { timeout: RUNS_ASKED_EVERY_MS * 2 },
      );

      expect(alert()).toBeNull();
    });

    it("drops what a refusal said once the run has been stopped as it asked", async () => {
      const { named, alert } = await refused(run({ epoch: 4, seed: 9, status: "running" }));
      await vi.waitFor(() => expect(alert()).not.toBeNull());

      act(() => named("Stop the run of Reference greenhouse")?.click());

      await vi.waitFor(() => expect(alert()).toBeNull());
    });

    it("says in the simulator's words a refusal of another kind, on the row", async () => {
      const { container, named } = await listed(
        run({ epoch: 4, seed: 9 }),
        () => new Response(JSON.stringify({ error: "the disk is read-only" }), { status: 500 }),
      );
      act(() => named(DELETE)?.click());
      act(() => named(DELETE)?.click());

      await vi.waitFor(() =>
        expect(container.querySelector('.landing-run [role="alert"]')?.textContent).toContain(
          "the disk is read-only",
        ),
      );
      expect(document.activeElement).toBe(named(DELETE));
    });

    it("offers it on every row, a run with files missing too", async () => {
      const { named } = await listed(
        run({ epoch: 4, seed: 9, damaged: true }),
        () => new Response(),
      );

      expect(named(DELETE)).toBeDefined();
    });
  });

  it("calls a run with files missing damaged, with no replay to open", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [run({ damaged: true })] },
      "Damaged",
    );

    expect(container.textContent).not.toContain("Finished");
    expect(link(container, "Replay")).toBeUndefined();
  });

  it("says what a fork came from, in its row", async () => {
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [
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
        ],
      },
      "forked",
    );

    expect(container.querySelector(".landing-run")?.textContent).toContain(
      "seed 1 · epoch 3 · forked from epoch 2 at Day 2, 01:00 · Oct 28",
    );
  });

  it("lists no more than the latest few", async () => {
    const many = Array.from({ length: 8 }, (_, epoch) => run({ epoch }));
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": many },
      "epoch 0",
    );
    expect(container.querySelectorAll(".landing-run")).toHaveLength(5);
  });

  it("lists a run still being computed, however many have been started since", async () => {
    // The newest first: the run computing and the one waiting are the oldest.
    const many = Array.from({ length: 8 }, (_, epoch) => run({ epoch }));
    many[6] = run({ epoch: 6, status: "queued" });
    many[7] = run({ epoch: 7, status: "running", progress: 0.5 });
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": many },
      "epoch 0",
    );
    const rows = [...container.querySelectorAll(".landing-run")].map((row) => row.textContent);
    expect(rows).toHaveLength(7);
    expect(rows[5]).toContain("epoch 6");
    expect(rows[6]).toContain("epoch 7");
  });

  it("says so when the simulator cannot be reached, and when the runs cannot be listed", async () => {
    const { container } = await shown(
      { "/api/scenarios": new Error("offline"), "/api/runs": new Error("offline") },
      "The runs kept cannot be listed: offline.",
    );
    expect(container.textContent).toContain("The simulator API is not reachable (offline).");
    expect(link(container, "Open the builder")).toBeDefined();
  });

  it("keeps the scenarios usable when only the runs cannot be listed", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": new Error("no run store") },
      "The runs kept cannot be listed: no run store.",
    );
    const input = container.querySelector("input");
    act(() => input?.click());
    expect(container.querySelectorAll('[role="option"]')[0]?.textContent).toBe(
      "Reference greenhousereference_greenhouse · organ-level tomato crop",
    );
  });
});
