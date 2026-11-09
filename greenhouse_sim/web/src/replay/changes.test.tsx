// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setLevel, setTarget } from "../plan/plan";
import { useSteering } from "../plan/useSteering";
import { render } from "../testing/render";
import {
  changesFor,
  type EpochChanges,
  giveToEpoch,
  LOOK_MS,
  type SteeredEpoch,
  saysSteering,
  steeredEpoch,
  takesChanges,
  whatBecameOf,
} from "./changes";

const REQUEST = "01794130623610413709-76b35bf1";
const CHANGES_URL = "/api/runs/run%201/epochs/2/changes";

function changes(over: Partial<EpochChanges> = {}): EpochChanges {
  return { status: "running", log: [], refused: [], waiting: [], done: [], ...over };
}

function logged(request: string, atS: number) {
  return {
    seq: 0,
    at_s: atS,
    given_s: atS - 30,
    by: "person:local_operator",
    what: { kind: "targets_changed", changes: [[atS, "heating_day", 24]] },
    request,
  };
}

/** A simulator that answers the change asked with `posted`, then each read of
 * the epoch's changes with the next of `looks`, the last one again after them. */
function simulator(posted: { status: number; body: unknown }, looks: (EpochChanges | null)[]) {
  const asked: { url: string; body: unknown }[] = [];
  let read = 0;
  const fetchFn = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      asked.push({ url, body: JSON.parse(String(init.body)) });
      return new Response(JSON.stringify(posted.body), { status: posted.status });
    }
    const look = looks[Math.min(read, looks.length - 1)];
    read += 1;
    return look === null ? new Response("{}", { status: 503 }) : new Response(JSON.stringify(look));
  });
  return { fetchFn: fetchFn as unknown as typeof fetch, asked, reads: () => read };
}

describe("which epochs take changes", () => {
  it("are those a worker works or will, and no other", () => {
    expect(takesChanges("queued")).toBe(true);
    expect(takesChanges("running")).toBe(true);
    for (const ended of ["finished", "failed", "interrupted"] as const) {
      expect(takesChanges(ended)).toBe(false);
    }
  });
});

describe("what became of a change asked of an epoch", () => {
  it("is the moment its worker logged it to take effect from, once it is done with it", () => {
    expect(
      whatBecameOf(
        changes({ log: [logged("other", 60), logged(REQUEST, 86_460)], done: ["other", REQUEST] }),
        REQUEST,
      ),
    ).toEqual({ status: "taken", atS: 86_460 });
  });

  it("is waiting while it is logged and its worker is not yet done with it", () => {
    // Logged before it is acted on, and maybe refused then (P17.8).
    expect(whatBecameOf(changes({ log: [logged(REQUEST, 60)] }), REQUEST)).toEqual({
      status: "waiting",
    });
  });

  it("is taken if the epoch ended with it logged and never done with, as a crash leaves it", () => {
    expect(
      whatBecameOf(changes({ status: "interrupted", log: [logged(REQUEST, 60)] }), REQUEST),
    ).toEqual({ status: "taken", atS: 60 });
  });

  it("is a refusal in the worker's words, also of one it logged and then refused", () => {
    const refused = { request: REQUEST, reason: "no heating loop whose target to change" };

    expect(
      whatBecameOf(
        changes({ log: [logged(REQUEST, 60)], refused: [refused], done: [REQUEST] }),
        REQUEST,
      ),
    ).toEqual({ status: "refused", reason: "no heating loop whose target to change" });
  });

  it("is waiting while the epoch runs and its worker has not taken it", () => {
    expect(whatBecameOf(changes({ waiting: [REQUEST] }), REQUEST)).toEqual({ status: "waiting" });
    expect(whatBecameOf(changes({ status: "queued", waiting: [REQUEST] }), REQUEST)).toEqual({
      status: "waiting",
    });
  });

  it("is never taken once the epoch has ended without taking it, and a fork is the way", () => {
    const became = whatBecameOf(changes({ status: "finished", waiting: [REQUEST] }), REQUEST);

    expect(became).toEqual({
      status: "refused",
      reason: "the run was finished before it took the change; a fork acts from a moment of it",
    });
  });
});

describe("the changes asked for what the panels set", () => {
  it("are the levels together and the targets together", () => {
    expect(
      changesFor([setLevel("heater", 1), setTarget("heating_day", 24), setLevel("fan", 0.5)]),
    ).toEqual([
      { kind: "levels", levels: { heater: 1, fan: 0.5 } },
      { kind: "targets", targets: { heating_day: 24 } },
    ]);
  });

  it("are a plant's work together, beside the levels (P22.3)", () => {
    const lower = { kind: "lower", plant_id: "p30", by_internodes: 1 } as const;
    const leaf = { kind: "remove_leaf", plant_id: "p30", leaf_id: "p30_l2" } as const;

    expect(changesFor([lower, setLevel("fan", 1), leaf])).toEqual([
      { kind: "levels", levels: { fan: 1 } },
      { kind: "work", actions: [lower, leaf] },
    ]);
  });

  it("are none for what a replay does not steer", () => {
    expect(changesFor([{ kind: "water", plant_id: "p30", amount_ml: 500 }])).toBeNull();
    expect(changesFor([{ kind: "set_level", device_id: "heater", level: "auto" }])).toBeNull();
  });
});

describe("giving a running epoch what its replay's panels set", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks it of the epoch, waits for its worker, and says the moment it took effect from", async () => {
    vi.useFakeTimers();
    const run = simulator({ status: 200, body: { request: REQUEST } }, [
      changes({ waiting: [REQUEST] }),
      changes({ log: [logged(REQUEST, 86_460)], done: [REQUEST] }),
    ]);

    const given = giveToEpoch("run 1", 2, [setTarget("heating_day", 24)], run.fetchFn);
    await vi.advanceTimersByTimeAsync(LOOK_MS);

    expect(await given).toEqual({ status: "given", atS: 86_460 });
    expect(run.asked).toEqual([
      { url: CHANGES_URL, body: { kind: "targets", targets: { heating_day: 24 } } },
    ]);
    expect(run.reads()).toBe(2);
  });

  it("asks a plant's work of the epoch as a plan of the viewer's own, as soon as it can", async () => {
    vi.useFakeTimers();
    const run = simulator({ status: 200, body: { request: REQUEST } }, [
      changes({ log: [logged(REQUEST, 86_460)], done: [REQUEST] }),
    ]);
    const lower = { kind: "lower", plant_id: "p30", by_internodes: 1 } as const;

    expect(await giveToEpoch("run 1", 2, [lower], run.fetchFn)).toEqual({
      status: "given",
      atS: 86_460,
    });
    const [asked] = run.asked;
    expect(asked?.body).toEqual({
      kind: "plan",
      plan: {
        plan_id: expect.stringMatching(/^plant_work_[0-9a-z]+$/),
        run_id: "run 1",
        epoch: 2,
        revision: 1,
        actions: [
          {
            action_id: "work_1",
            action: lower,
            timing: { kind: "asap" },
            proposed_by: { kind: "person", id: "local_operator" },
          },
        ],
      },
    });
  });

  it("says the simulator's refusal, as of an epoch that ended before the change was asked", async () => {
    const run = simulator(
      {
        status: 409,
        body: { error: "epoch 2 of run 1 is finished: it takes no more changes" },
      },
      [],
    );

    const given = await giveToEpoch("run 1", 2, [setLevel("heater", 1)], run.fetchFn);

    expect(given).toEqual({
      status: "refused",
      reason: "epoch 2 of run 1 is finished: it takes no more changes",
    });
    expect(run.reads()).toBe(0);
  });

  it("waits past a change logged and not yet done with, and says the refusal that follows", async () => {
    vi.useFakeTimers();
    const refused = { request: REQUEST, reason: "local_operator may not change heating_day" };
    const run = simulator({ status: 200, body: { request: REQUEST } }, [
      changes({ log: [logged(REQUEST, 60)] }),
      changes({ log: [logged(REQUEST, 60)], refused: [refused], done: [REQUEST] }),
    ]);

    const given = giveToEpoch("run 1", 2, [setTarget("heating_day", 24)], run.fetchFn);
    await vi.advanceTimersByTimeAsync(LOOK_MS);

    expect(await given).toEqual({ status: "refused", reason: refused.reason });
    expect(run.reads()).toBe(2);
  });

  it("says the worker's refusal", async () => {
    const run = simulator({ status: 200, body: { request: REQUEST } }, [
      changes({ refused: [{ request: REQUEST, reason: "may not set heater" }] }),
    ]);

    expect(await giveToEpoch("run 1", 2, [setLevel("heater", 1)], run.fetchFn)).toEqual({
      status: "refused",
      reason: "may not set heater",
    });
  });

  it("stops waiting, and says so, once the simulator cannot be read", async () => {
    vi.useFakeTimers();
    const run = simulator({ status: 200, body: { request: REQUEST } }, [null]);

    const given = giveToEpoch("run 1", 2, [setLevel("heater", 1)], run.fetchFn);
    await vi.advanceTimersByTimeAsync(10 * LOOK_MS);

    expect(await given).toEqual({
      status: "refused",
      reason: "the simulator could not be reached to say whether the run took the change",
    });
    expect(run.reads()).toBe(5);
  });

  it("asks nothing it does not steer", async () => {
    const run = simulator({ status: 200, body: { request: REQUEST } }, []);

    const given = await giveToEpoch(
      "run 1",
      2,
      [{ kind: "water", plant_id: "p30", amount_ml: 500 }],
      run.fetchFn,
    );

    expect(given.status).toBe("refused");
    expect(run.asked).toEqual([]);
  });
});

describe("the epoch a replay steers, as it ends", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  let steering: ReturnType<typeof useSteering> | null = null;
  function Steered({ steer }: { steer: SteeredEpoch }) {
    steering = useSteering(steer.epoch, {}, steer.give);
    return null;
  }

  it("is the same epoch, so that a change left untaken as it ends is still said", async () => {
    vi.useFakeTimers();
    // The worker has not taken the change by the time the epoch ends.
    const run = simulator({ status: 200, body: { request: REQUEST } }, [
      changes({ waiting: [REQUEST] }),
      changes({ status: "finished", waiting: [REQUEST] }),
    ]);
    const give = (actions: Parameters<typeof giveToEpoch>[2]) =>
      giveToEpoch("run 1", 2, actions, run.fetchFn);
    const running = steeredEpoch("run 1", 2, give, "running");
    const shown = render(<Steered steer={running} />);
    act(() => steering?.setTargets({ heating_day: 24 }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // The position says it has ended before the worker's answer is read.
    const ended = steeredEpoch("run 1", 2, give, "finished");
    shown.rerender(<Steered steer={ended} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOOK_MS);
    });

    expect(ended.epoch).toBe(running.epoch);
    expect(ended.computing).toBe(false);
    expect(steering?.refusal).toBe(
      "the run was finished before it took the change; a fork acts from a moment of it",
    );
    expect(
      saysSteering(ended.computing, steering ?? { waiting: 0, taken: null, refusal: null }),
    ).toBe(true);
    shown.unmount();
  });

  it("is said while it is computed, and after only while something of a change is", () => {
    const none = { waiting: 0, taken: null, refusal: null };
    expect(saysSteering(true, none)).toBe(true);
    expect(saysSteering(false, none)).toBe(false);
    expect(saysSteering(false, { ...none, waiting: 1 })).toBe(true);
    expect(saysSteering(false, { ...none, taken: 60 })).toBe(true);
    expect(saysSteering(false, { ...none, refusal: "no" })).toBe(true);
  });
});
