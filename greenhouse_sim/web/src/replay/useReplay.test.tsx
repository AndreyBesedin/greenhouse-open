// @vitest-environment jsdom
import { act, StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import type { PositionState } from "./position";
import { POSITION_LOST, useReplay } from "./useReplay";

function state(more: Partial<PositionState> = {}): PositionState {
  return {
    position_id: "p1",
    scenario_id: "reference_greenhouse",
    run_id: "run-1",
    epoch: 0,
    layout: "default",
    seed: 1,
    status: "finished",
    started_at: "2026-03-01T00:00:00Z",
    simulated_now: "2026-03-01T00:00:00Z",
    time_s: 0,
    day: 0,
    playing: false,
    following: false,
    seconds_per_day: 10,
    frontier_s: 3 * DAY_S,
    duration_s: 3 * DAY_S,
    start_s: 0,
    fork: null,
    targets: [],
    commands: [],
    crop: [],
    ...more,
  };
}

interface Call {
  method: string;
  url: string;
}

/** A simulator that opens positions p1, p2, …, and answers each with the
 * state it was last given. */
function simulator(first: Partial<PositionState> = {}) {
  const calls: Call[] = [];
  let opened = 0;
  const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ method: init?.method ?? "GET", url });
    if (url.endsWith("/positions")) {
      opened += 1;
      return Response.json(state({ ...first, position_id: `p${opened}` }));
    }
    if (url.includes("/seek")) {
      return Response.json(state({ ...first, time_s: 3600 }));
    }
    return Response.json(state(first));
  }) as unknown as typeof fetch;
  return { fetchFn, calls };
}

function Probe({
  fetchFn,
  runId = "run-1",
  following = false,
}: {
  fetchFn: typeof fetch;
  runId?: string;
  following?: boolean;
}) {
  const replay = useReplay(runId, 0, fetchFn, following);
  return (
    <div>
      <span data-testid="status">{replay.load.status}</span>
      <span data-testid="refused">{replay.refused}</span>
      <span data-testid="time">
        {replay.load.status === "loaded" ? replay.load.position.time_s : ""}
      </span>
      <button type="button" onClick={() => replay.command("play")}>
        play
      </button>
      <button type="button" onClick={() => replay.command("follow")}>
        follow
      </button>
      <button type="button" onClick={() => replay.seek(3600)}>
        seek
      </button>
      <button type="button" onClick={() => replay.seek(7200)}>
        seek later
      </button>
    </div>
  );
}

/** A simulator whose answers to seeks and to looks are held until the test
 * lets each come, so that they can arrive in any order. */
function held(first: Partial<PositionState> = {}) {
  const seeks: ((timeS: number) => void)[] = [];
  const looks: ((timeS: number) => void)[] = [];
  let opened = 0;
  const fetchFn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/positions")) {
      opened += 1;
      return Promise.resolve(Response.json(state({ ...first, position_id: `p${opened}` })));
    }
    if (url.endsWith("/close")) {
      return Promise.resolve(Response.json({}));
    }
    return new Promise<Response>((resolve) => {
      const answer = (timeS: number) => resolve(Response.json(state({ ...first, time_s: timeS })));
      (url.includes("/seek") ? seeks : looks).push(answer);
      init?.signal?.addEventListener("abort", () => resolve(new Response("{}", { status: 499 })));
    });
  }) as unknown as typeof fetch;
  return { fetchFn, seeks, looks };
}

function pressed(container: HTMLElement, name: string): void {
  const control = [...container.querySelectorAll("button")].find((b) => b.textContent === name);
  act(() => control?.click());
}

/** The moments asked for by the seeks sent, in order. */
function seekedTo(fetchFn: typeof fetch): (string | undefined)[] {
  return vi
    .mocked(fetchFn)
    .mock.calls.map(([input]) => String(input))
    .filter((url) => url.includes("/seek"))
    .map((url) => url.split("t=")[1]);
}

function shownTime(container: HTMLElement): string | null | undefined {
  return container.querySelector('[data-testid="time"]')?.textContent;
}

async function settle(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("a stored epoch replayed", () => {
  let rendered: Rendered | undefined;
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    rendered?.unmount();
    vi.useRealTimers();
  });

  it("opens a position over the epoch, and closes it when the page is left", async () => {
    const { fetchFn, calls } = simulator();
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();

    expect(rendered.container.querySelector('[data-testid="status"]')?.textContent).toBe("loaded");
    expect(calls[0]).toEqual({ method: "POST", url: "/api/runs/run-1/epochs/0/positions" });

    rendered.unmount();
    rendered = undefined;
    expect(calls.at(-1)).toEqual({ method: "POST", url: "/api/positions/p1/close" });
  });

  it("opens following the newest day when asked: never shown at the start on its way", async () => {
    const frontier = 2 * DAY_S;
    const asked: string[] = [];
    let answerFollow: (response: Response) => void = () => undefined;
    const fetchFn = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      asked.push(url);
      if (url.endsWith("/follow")) {
        return new Promise<Response>((resolve) => {
          answerFollow = resolve;
        });
      }
      return Promise.resolve(Response.json(state({ status: "running", frontier_s: frontier })));
    }) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} following />);
    await settle();
    await settle();

    expect(asked).toEqual(["/api/runs/run-1/epochs/0/positions", "/api/positions/p1/follow"]);
    expect(rendered.container.querySelector('[data-testid="status"]')?.textContent).toBe("loading");

    await act(async () => {
      answerFollow(
        Response.json(
          state({ status: "running", frontier_s: frontier, time_s: frontier, following: true }),
        ),
      );
      await Promise.resolve();
    });
    await settle();
    expect(shownTime(rendered.container)).toBe(String(frontier));
  });

  it("does not follow unless asked", async () => {
    const { fetchFn, calls } = simulator({ status: "running" });
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();

    expect(calls.map((c) => c.url)).toEqual(["/api/runs/run-1/epochs/0/positions"]);
  });

  it("shows the run where it was opened, and says why, if it cannot follow", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/follow")
        ? new Response(JSON.stringify({ error: "no such position" }), { status: 404 })
        : Response.json(state({ status: "running" })),
    ) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} following />);
    await settle();
    await settle();
    await settle();

    expect(rendered.container.querySelector('[data-testid="status"]')?.textContent).toBe("loaded");
    expect(rendered.container.querySelector('[data-testid="refused"]')?.textContent).toBe(
      "no such position",
    );
  });

  it("closes the position it was following into when the page is left on the way", async () => {
    let answerFollow: (response: Response) => void = () => undefined;
    const asked: string[] = [];
    const fetchFn = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      asked.push(url);
      if (url.endsWith("/follow")) {
        return new Promise<Response>((resolve) => {
          answerFollow = resolve;
        });
      }
      return Promise.resolve(Response.json(state({ status: "running" })));
    }) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} following />);
    await settle();
    await settle();

    rendered.unmount();
    rendered = undefined;
    expect(asked.at(-1)).toBe("/api/positions/p1/close");
    answerFollow(Response.json(state({ status: "running", following: true })));
    await settle();
  });

  it("closes the first of the two positions a strict page opens", async () => {
    const { fetchFn, calls } = simulator();
    rendered = render(
      <StrictMode>
        <Probe fetchFn={fetchFn} />
      </StrictMode>,
    );
    await settle();
    await settle();

    const opens = calls.filter((c) => c.url.endsWith("/positions"));
    const closes = calls.filter((c) => c.url.endsWith("/close"));
    expect(opens).toHaveLength(2);
    expect(closes.map((c) => c.url)).toEqual(["/api/positions/p1/close"]);
  });

  it("asks again while the epoch is being computed, and not once it is done", async () => {
    const running = simulator({ status: "running" });
    rendered = render(<Probe fetchFn={running.fetchFn} />);
    await settle();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(running.calls.filter((c) => c.method === "GET").length).toBeGreaterThanOrEqual(2);
    rendered.unmount();

    const done = simulator({ status: "finished" });
    rendered = render(<Probe fetchFn={done.fetchFn} />);
    await settle();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(done.calls.filter((c) => c.method === "GET")).toHaveLength(0);
  });

  it("says so and stops asking once the simulator has let the position go", async () => {
    let restarted = false;
    const answers = simulator({ status: "running" });
    const looks: string[] = [];
    const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === undefined) {
        looks.push(String(input));
        if (restarted) {
          return Response.json({ error: "no position 'p1'" }, { status: 404 });
        }
      }
      return answers.fetchFn(input, init);
    }) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    const { container } = rendered;
    const refused = () => container.querySelector('[data-testid="refused"]')?.textContent;
    expect(refused()).toBe("");

    restarted = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(refused()).toBe(POSITION_LOST);
    // The last good place stays, and no more is asked of a position that is gone.
    expect(container.querySelector('[data-testid="status"]')?.textContent).toBe("loaded");
    const asked = looks.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(looks).toHaveLength(asked);
  });

  it("goes on asking through a look that failed for any other reason", async () => {
    let down = false;
    const answers = simulator({ status: "running" });
    const looks: string[] = [];
    const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === undefined) {
        looks.push(String(input));
        if (down) {
          return new Response("Bad Gateway", { status: 502 });
        }
      }
      return answers.fetchFn(input, init);
    }) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    down = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    const asked = looks.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(looks.length).toBeGreaterThan(asked);
    expect(rendered.container.querySelector('[data-testid="refused"]')?.textContent).toBe("");
  });

  it("keeps the position a command or a seek answers with", async () => {
    const { fetchFn, calls } = simulator();
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();

    const seek = [...rendered.container.querySelectorAll("button")].find(
      (b) => b.textContent === "seek",
    );
    act(() => seek?.click());
    await settle();

    expect(calls.some((c) => c.url === "/api/positions/p1/seek?t=3600")).toBe(true);
    expect(rendered.container.querySelector('[data-testid="time"]')?.textContent).toBe("3600");
  });

  it("says why a move was refused, keeps the place it had, and clears it on the next", async () => {
    let gone = true;
    const answers = simulator();
    const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      gone && String(input).endsWith("/play")
        ? Response.json({ error: "no position 'p1'" }, { status: 404 })
        : answers.fetchFn(input, init),
    ) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    const { container } = rendered;
    const refused = () => container.querySelector('[data-testid="refused"]')?.textContent;
    expect(refused()).toBe("");

    pressed(container, "play");
    await settle();
    await settle();

    expect(refused()).toBe("no position 'p1'");
    expect(container.querySelector('[data-testid="status"]')?.textContent).toBe("loaded");
    expect(shownTime(container)).toBe("0");

    gone = false;
    pressed(container, "play");
    await settle();
    await settle();
    expect(refused()).toBe("");
  });

  it("says why a position could not be opened", async () => {
    const fetchFn = vi.fn(
      async () => new Response("{}", { status: 404 }),
    ) as unknown as typeof fetch;
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();

    expect(rendered.container.querySelector('[data-testid="status"]')?.textContent).toBe(
      "unavailable",
    );
  });
});

describe("the answers a replay takes, in the order they were asked", () => {
  let rendered: Rendered | undefined;
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    rendered?.unmount();
    vi.useRealTimers();
  });

  it("sends one seek at a time, and after it only the latest asked for", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();

    // A drag: three moves while the first is on its way.
    pressed(rendered.container, "seek");
    pressed(rendered.container, "seek later");
    pressed(rendered.container, "seek");
    pressed(rendered.container, "seek later");
    await settle();
    expect(seeks).toHaveLength(1);

    // The first's answer is to an earlier word than the page's latest.
    seeks[0]?.(3600);
    await settle();
    expect(shownTime(rendered.container)).toBe("0");
    expect(seekedTo(fetchFn)).toEqual(["3600", "7200"]);

    seeks[1]?.(7200);
    await settle();
    expect(shownTime(rendered.container)).toBe("7200");
    expect(seeks).toHaveLength(2);
  });

  it("sends the next seek at once when none is on its way", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    pressed(rendered.container, "seek");
    seeks[0]?.(3600);
    await settle();
    expect(shownTime(rendered.container)).toBe("3600");

    pressed(rendered.container, "seek later");
    await settle();

    expect(seekedTo(fetchFn)).toEqual(["3600", "7200"]);
  });

  it("sends no seek left waiting once the replay is another", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Probe fetchFn={fetchFn} runId="run-1" />);
    await settle();
    pressed(rendered.container, "seek");
    pressed(rendered.container, "seek later");

    rendered.rerender(<Probe fetchFn={fetchFn} runId="run-2" />);
    await settle();
    seeks[0]?.(3600);
    await settle();

    expect(seeks).toHaveLength(1);
  });

  it("sends no seek left waiting once the position is told to follow", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    pressed(rendered.container, "seek");
    pressed(rendered.container, "seek later");
    pressed(rendered.container, "follow");

    seeks[0]?.(3600);
    await settle();

    expect(seeks).toHaveLength(1);
  });

  it("drops the answer to a seek that is asked of a replay no longer shown", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Probe fetchFn={fetchFn} runId="run-1" />);
    await settle();
    pressed(rendered.container, "seek");

    rendered.rerender(<Probe fetchFn={fetchFn} runId="run-2" />);
    await settle();
    expect(shownTime(rendered.container)).toBe("0");
    seeks[0]?.(3600);
    await settle();

    expect(shownTime(rendered.container)).toBe("0");
  });

  it("drops a look that began before a seek, when it comes back after it", async () => {
    const { fetchFn, seeks, looks } = held({ status: "running" });
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(looks).toHaveLength(1);

    pressed(rendered.container, "seek later");
    seeks[0]?.(7200);
    await settle();
    looks[0]?.(100);
    await settle();

    expect(shownTime(rendered.container)).toBe("7200");
  });

  it("drops a look that comes back while a seek still waits", async () => {
    const { fetchFn, seeks, looks } = held({ status: "running" });
    rendered = render(<Probe fetchFn={fetchFn} />);
    await settle();
    pressed(rendered.container, "seek later");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(looks).toHaveLength(1);

    looks[0]?.(100);
    await settle();
    expect(shownTime(rendered.container)).toBe("0");
    seeks[0]?.(7200);
    await settle();

    expect(shownTime(rendered.container)).toBe("7200");
  });
});

describe("the moment a replay is heading for", () => {
  let rendered: Rendered | undefined;
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    rendered?.unmount();
    vi.useRealTimers();
  });

  function Heading({ fetchFn, runId = "run-1" }: { fetchFn: typeof fetch; runId?: string }) {
    const replay = useReplay(runId, 0, fetchFn);
    return (
      <div>
        <span data-testid="heading">{String(replay.heading)}</span>
        <button type="button" onClick={() => replay.seek(3600)}>
          seek
        </button>
        <button type="button" onClick={() => replay.seek(7200)}>
          seek later
        </button>
      </div>
    );
  }

  const heading = (container: HTMLElement) =>
    container.querySelector('[data-testid="heading"]')?.textContent;

  it("is the latest sought, until the latest asked is answered", async () => {
    const { fetchFn, seeks } = held();
    rendered = render(<Heading fetchFn={fetchFn} />);
    await settle();
    expect(heading(rendered.container)).toBe("null");

    pressed(rendered.container, "seek");
    expect(heading(rendered.container)).toBe("3600");
    pressed(rendered.container, "seek later");
    expect(heading(rendered.container)).toBe("7200");

    // An earlier answer is to an earlier word: the page is still heading on.
    seeks[0]?.(3600);
    await settle();
    expect(heading(rendered.container)).toBe("7200");

    seeks.at(-1)?.(7200);
    await settle();
    expect(heading(rendered.container)).toBe("null");
  });

  it("is let go when the seek is refused, so that the next starts from the position", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes("/seek")
        ? new Response("{}", { status: 503 })
        : Response.json(state()),
    ) as unknown as typeof fetch;
    rendered = render(<Heading fetchFn={fetchFn} />);
    await settle();

    pressed(rendered.container, "seek");
    expect(heading(rendered.container)).toBe("3600");
    await settle();

    expect(heading(rendered.container)).toBe("null");
  });

  it("is let go with the replay it was of", async () => {
    const { fetchFn } = held();
    rendered = render(<Heading fetchFn={fetchFn} runId="run-1" />);
    await settle();
    pressed(rendered.container, "seek");

    rendered.rerender(<Heading fetchFn={fetchFn} runId="run-2" />);
    await settle();

    expect(heading(rendered.container)).toBe("null");
  });
});
