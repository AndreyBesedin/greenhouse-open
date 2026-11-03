// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import { forkEpoch, whyNoFork } from "./fork";
import { useFork } from "./useFork";

const RUN = {
  run_id: "run-2",
  epoch: 4,
  scenario_id: "reference_greenhouse",
  seed: null,
  layout: "default",
  status: "queued",
  frontier_s: DAY_S,
  duration_s: 3 * DAY_S,
  progress: 1 / 3,
  created_at: null,
  size_bytes: 10,
  start_s: DAY_S,
  fork: {
    run_id: "run-1",
    epoch: 0,
    at_s: DAY_S,
    start_s: DAY_S,
    digest: "d",
    checkpoint_sha256: "c",
    inherited: 0,
    layout: null,
  },
};

function answering(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("asking for a fork", () => {
  it("names the moment, the layout and the changes, and says the fork started", async () => {
    const fetchFn = answering(200, RUN);

    const answer = await forkEpoch(
      "run 1",
      0,
      {
        timeS: 1234.5,
        layout: "default~heater:1:0",
        changes: [{ kind: "levels", levels: { heater: 0.5 } }],
      },
      fetchFn,
    );

    expect(answer).toEqual({ status: "started", runId: "run-2", epoch: 4 });
    const [url, init] = vi.mocked(fetchFn).mock.calls[0] ?? [];
    expect(url).toBe("/api/runs/run%201/epochs/0/forks?t=1234.5&layout=default~heater%3A1%3A0");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual([{ kind: "levels", levels: { heater: 0.5 } }]);
  });

  it("says why the simulator refused it, or that it could not be reached", async () => {
    expect(
      await forkEpoch("r", 0, { timeS: 0 }, answering(409, { error: "there is nothing" })),
    ).toEqual({ status: "unavailable", reason: "there is nothing" });
    const unreachable = vi.fn(async () => {
      throw new Error("no");
    }) as typeof fetch;
    expect(await forkEpoch("r", 0, { timeS: 0 }, unreachable)).toEqual({
      status: "unavailable",
      reason: "the simulator could not be reached",
    });
    expect((await forkEpoch("r", 0, { timeS: 0 }, answering(200, { no: "run" }))).status).toBe(
      "unavailable",
    );
  });

  it("says why there can be none at the end of a run, and nothing elsewhere", () => {
    expect(whyNoFork({ time_s: DAY_S, duration_s: DAY_S })).toMatch(/ends here/);
    expect(whyNoFork({ time_s: DAY_S / 2, duration_s: DAY_S })).toBeNull();
    expect(whyNoFork({ time_s: DAY_S / 2, duration_s: null })).toBeNull();
  });
});

describe("a replay's fork", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function hook(fetchFn: typeof fetch, goTo: (address: string) => void) {
    let controls: ReturnType<typeof useFork> | undefined;
    function Probe() {
      controls = useFork({ runId: "run-1", epoch: 0 }, { fetchFn, goTo });
      return null;
    }
    rendered = render(<Probe />);
    return () => {
      if (controls === undefined) {
        throw new Error("not rendered");
      }
      return controls;
    };
  }

  it("goes to the fork once it is started", async () => {
    const goTo = vi.fn();
    const controls = hook(answering(200, RUN), goTo);

    await act(async () => {
      await controls().fork({ timeS: DAY_S });
    });

    expect(goTo).toHaveBeenCalledWith("/replay?run=run-2&epoch=4");
    expect(controls().forking).toBe(true);
  });

  it("makes one at a time, whatever asks while one is under way", async () => {
    const fetchFn = answering(200, RUN);
    const controls = hook(fetchFn, vi.fn());

    await act(async () => {
      await Promise.all([controls().fork({ timeS: 1 }), controls().fork({ timeS: 2 })]);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("stays, says why and can be asked again if it was refused", async () => {
    const goTo = vi.fn();
    const controls = hook(answering(409, { error: "the run ends there" }), goTo);

    let answered: string | null = null;
    await act(async () => {
      answered = await controls().fork({ timeS: DAY_S });
    });

    expect(answered).toBe("the run ends there");
    expect(goTo).not.toHaveBeenCalled();
    expect(controls().forking).toBe(false);
    expect(controls().refused).toBe("the run ends there");
  });
});
