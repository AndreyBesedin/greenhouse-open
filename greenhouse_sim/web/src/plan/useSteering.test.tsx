// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { render } from "../testing/render";
import type { Action } from "./generated/planTypes";
import type { Given } from "./plan";
import { type Give, NOT_STEERED, STEER_PAUSE_MS, useSteering } from "./useSteering";

type Steering = ReturnType<typeof useSteering>;
let steering: Steering | null = null;

/** Steered through `give`, whatever reaches the run, under the name `steered`. */
function SteeredBy({
  steered,
  give,
  shown = {},
}: {
  steered: string | null;
  give: Give;
  shown?: Readonly<Record<string, number>>;
}) {
  steering = useSteering(steered, shown, give);
  return null;
}

/** A run that takes every change at once, or refuses each for `refusal`, and
 * keeps what it was asked. */
function taking(refusal: string | null = null) {
  const asked: Action[][] = [];
  const give: Give = async (actions) => {
    asked.push(actions);
    return refusal === null ? { status: "given" } : { status: "refused", reason: refusal };
  };
  return { give, asked };
}

/** A run that answers each change once `answer` is called, as an epoch's
 * worker answers once it has taken it. */
function answeredLater() {
  const asked: unknown[] = [];
  let answer: (given: Given) => void = () => undefined;
  const give: Give = (actions) => {
    asked.push(actions);
    return new Promise((resolve) => {
      answer = resolve;
    });
  };
  return { give, asked, answer: (given: Given) => answer(given) };
}

async function waited(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("a run steered from the panels", () => {
  afterEach(() => {
    vi.useRealTimers();
    steering = null;
  });

  it("gives the levels a drag set once it rests, as one change", async () => {
    vi.useFakeTimers();
    const run = taking();
    render(<SteeredBy steered="epoch#0" give={run.give} shown={{ fan: 0 }} />);

    act(() => steering?.steer({ fan: 0.2 }));
    act(() => steering?.steer({ fan: 0.6 }));
    act(() => steering?.steer({ roof_vent: 1 }));
    await waited(STEER_PAUSE_MS - 1);
    expect(run.asked).toEqual([]);
    expect(steering?.asked).toEqual({ fan: 0.6, roof_vent: 1 });

    await waited(1);
    expect(run.asked).toEqual([
      [
        { kind: "set_level", device_id: "fan", level: 0.6 },
        { kind: "set_level", device_id: "roof_vent", level: 1 },
      ],
    ]);
    expect(steering?.refusal).toBeNull();
    expect(steering?.given).toBe(1);
  });

  it("shows a level as asked until the run has it", async () => {
    vi.useFakeTimers();
    const run = taking();
    const shown = render(<SteeredBy steered="epoch#0" give={run.give} shown={{ fan: 0 }} />);

    act(() => steering?.steer({ fan: 0.6 }));
    await waited(STEER_PAUSE_MS);
    expect(steering?.asked).toEqual({ fan: 0.6 });

    shown.rerender(<SteeredBy steered="epoch#0" give={run.give} shown={{ fan: 0.6 }} />);
    expect(steering?.asked).toEqual({});
  });

  it("says why a change was refused, and stops showing what was refused", async () => {
    vi.useFakeTimers();
    const run = taking("not authorised");
    render(<SteeredBy steered="epoch#0" give={run.give} shown={{ fan: 0 }} />);

    act(() => steering?.steer({ fan: 0.6 }));
    await waited(STEER_PAUSE_MS);

    expect(steering?.refusal).toBe("not authorised");
    expect(steering?.asked).toEqual({});
  });

  it("gives targets at once", async () => {
    vi.useFakeTimers();
    const run = taking();
    render(<SteeredBy steered="epoch#0" give={run.give} />);

    act(() => steering?.setTargets({ heating_day: 22 }));
    await waited(0);

    expect(run.asked).toEqual([[{ kind: "set_target", target: "heating_day", value_c: 22 }]]);
  });

  it("gives what is asked of a plant at once", async () => {
    vi.useFakeTimers();
    const run = taking();
    render(<SteeredBy steered="epoch#0" give={run.give} />);

    act(() => steering?.act([{ kind: "lower", plant_id: "p30", by_internodes: 1 }]));
    await waited(0);

    expect(run.asked).toEqual([[{ kind: "lower", plant_id: "p30", by_internodes: 1 }]]);
  });

  it("refuses what reaches no run", async () => {
    expect(await NOT_STEERED([{ kind: "set_target", target: "heating_day", value_c: 22 }])).toEqual(
      { status: "refused", reason: "no run is steered" },
    );
  });
});

describe("a run steered through whatever gives it its changes", () => {
  afterEach(() => {
    steering = null;
  });

  it("says a change is waiting until the run answers, then the moment it took effect from", async () => {
    const run = answeredLater();
    render(<SteeredBy steered="epoch#0" give={run.give} />);

    act(() => steering?.setTargets({ heating_day: 24 }));
    expect(steering?.waiting).toBe(1);
    expect(steering?.taken).toBeNull();
    expect(run.asked).toEqual([[{ kind: "set_target", target: "heating_day", value_c: 24 }]]);

    await act(async () => run.answer({ status: "given", atS: 86_460 }));
    expect(steering?.waiting).toBe(0);
    expect(steering?.taken).toBe(86_460);
    expect(steering?.refusal).toBeNull();
  });

  it("says why the run refused a change, and keeps the moment of none", async () => {
    const run = answeredLater();
    render(<SteeredBy steered="epoch#0" give={run.give} />);

    act(() => steering?.setTargets({ heating_day: 24 }));
    await act(async () => run.answer({ status: "refused", reason: "it takes no more changes" }));

    expect(steering?.refusal).toBe("it takes no more changes");
    expect(steering?.taken).toBeNull();
  });

  it("drops what a run steered before says, once another is steered", async () => {
    const run = answeredLater();
    const shown = render(<SteeredBy steered="epoch#0" give={run.give} />);
    act(() => steering?.setTargets({ heating_day: 24 }));

    shown.rerender(<SteeredBy steered={null} give={run.give} />);
    await act(async () => run.answer({ status: "refused", reason: "too late" }));

    expect(steering?.refusal).toBeNull();
    expect(steering?.waiting).toBe(0);
  });

  it("keeps what became of a change while the same run is steered", async () => {
    // A replay's epoch is the run steered whether or not it is still computed.
    const run = answeredLater();
    const shown = render(<SteeredBy steered="epoch#0" give={run.give} />);
    act(() => steering?.setTargets({ heating_day: 24 }));

    shown.rerender(<SteeredBy steered="epoch#0" give={run.give} />);
    await act(async () => run.answer({ status: "refused", reason: "it ended first" }));

    expect(steering?.refusal).toBe("it ended first");
  });

  it("gives nothing while no run is steered", () => {
    const run = answeredLater();
    render(<SteeredBy steered={null} give={run.give} />);

    act(() => steering?.setTargets({ heating_day: 24 }));

    expect(run.asked).toEqual([]);
    expect(steering?.waiting).toBe(0);
  });
});
