import { afterEach, describe, expect, it, vi } from "vitest";

import { setLevel, setTarget } from "../plan/plan";
import {
  changesFor,
  type EpochChanges,
  giveToEpoch,
  LOOK_MS,
  takesChanges,
  whatBecameOf,
} from "./changes";

const REQUEST = "01794130623610413709-76b35bf1";
const CHANGES_URL = "/api/runs/run%201/epochs/2/changes";

function changes(over: Partial<EpochChanges> = {}): EpochChanges {
  return { status: "running", log: [], refused: [], waiting: [], ...over };
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
  it("is the moment its worker logged it to take effect from", () => {
    expect(
      whatBecameOf(changes({ log: [logged("other", 60), logged(REQUEST, 86_460)] }), REQUEST),
    ).toEqual({ status: "taken", atS: 86_460 });
  });

  it("is a refusal in the worker's words, also of one it logged and then refused", () => {
    const refused = { request: REQUEST, reason: "no heating loop whose target to change" };

    expect(
      whatBecameOf(changes({ log: [logged(REQUEST, 60)], refused: [refused] }), REQUEST),
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

  it("are none for what a replay does not steer", () => {
    expect(changesFor([{ kind: "lower", plant_id: "p30", by_internodes: 1 }])).toBeNull();
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
      changes({ log: [logged(REQUEST, 86_460)] }),
    ]);

    const given = giveToEpoch("run 1", 2, [setTarget("heating_day", 24)], run.fetchFn);
    await vi.advanceTimersByTimeAsync(LOOK_MS);

    expect(await given).toEqual({ status: "given", atS: 86_460 });
    expect(run.asked).toEqual([
      { url: CHANGES_URL, body: { kind: "targets", targets: { heating_day: 24 } } },
    ]);
    expect(run.reads()).toBe(2);
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
      [{ kind: "lower", plant_id: "p30", by_internodes: 1 }],
      run.fetchFn,
    );

    expect(given.status).toBe("refused");
    expect(run.asked).toEqual([]);
  });
});
