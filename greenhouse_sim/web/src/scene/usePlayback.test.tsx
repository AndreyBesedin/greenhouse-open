// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { render } from "../testing/render";
import { type PlaybackLoad, usePlayback } from "./playback";

// What the hook gives on every render, in order.
let seen: { scenarioId: string | null; load: PlaybackLoad }[] = [];

function Following({ scenarioId, fetchFn }: { scenarioId: string | null; fetchFn: typeof fetch }) {
  const [load] = usePlayback(scenarioId, fetchFn);
  seen.push({ scenarioId, load });
  return null;
}

function playing(runId: string, timeS: number): Response {
  return new Response(
    JSON.stringify({
      run_id: runId,
      layout: "default",
      epoch: 0,
      simulated_now: "2026-03-01T00:00:00Z",
      time_s: timeS,
      day: 0,
      playing: true,
      seconds_per_day: 10,
      worked_out_s: 86_400,
    }),
  );
}

async function settled(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

describe("a followed run's playback, polled", () => {
  afterEach(() => {
    vi.useRealTimers();
    seen = [];
  });

  it("is never another scenario's, not even on the first render after a switch", async () => {
    vi.useFakeTimers();
    const fetchFn = vi.fn(async (url: string) =>
      url.includes("/a/") ? playing("a-run", 600) : new Response("", { status: 404 }),
    ) as unknown as typeof fetch;
    const shown = render(<Following scenarioId="a" fetchFn={fetchFn} />);
    await settled();
    expect(seen.at(-1)?.load).toMatchObject({ status: "loaded", state: { runId: "a-run" } });

    seen = [];
    shown.rerender(<Following scenarioId="b" fetchFn={fetchFn} />);
    await settled();

    // B's first render says it is loading; A's clock is never B's.
    expect(seen[0]).toEqual({ scenarioId: "b", load: { status: "loading" } });
    expect(seen.every(({ load }) => load.status !== "loaded")).toBe(true);
    expect(seen.at(-1)?.load).toEqual({ status: "unstarted" });
    shown.unmount();
  });

  it("says an answer it cannot read, and asks again", async () => {
    vi.useFakeTimers();
    const answers = [new Response("{ truncated"), playing("a-run", 600)];
    const fetchFn = vi.fn(
      async () => answers.shift() ?? playing("a-run", 660),
    ) as unknown as typeof fetch;
    const shown = render(<Following scenarioId="a" fetchFn={fetchFn} />);
    await settled();
    expect(seen.at(-1)?.load.status).toBe("unavailable");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(seen.at(-1)?.load).toMatchObject({ status: "loaded", state: { timeS: 600 } });
    shown.unmount();
  });
});
