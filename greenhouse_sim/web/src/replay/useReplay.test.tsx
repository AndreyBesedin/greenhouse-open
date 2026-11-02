// @vitest-environment jsdom
import { act, StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import type { PositionState } from "./position";
import { useReplay } from "./useReplay";

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

function Probe({ fetchFn }: { fetchFn: typeof fetch }) {
  const replay = useReplay("run-1", 0, fetchFn);
  return (
    <div>
      <span data-testid="status">{replay.load.status}</span>
      <span data-testid="time">
        {replay.load.status === "loaded" ? replay.load.position.time_s : ""}
      </span>
      <button type="button" onClick={() => replay.command("play")}>
        play
      </button>
      <button type="button" onClick={() => replay.seek(3600)}>
        seek
      </button>
    </div>
  );
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
