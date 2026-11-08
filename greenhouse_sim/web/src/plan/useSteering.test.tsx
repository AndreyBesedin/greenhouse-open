// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlaybackLoad } from "../scene/playback";
import { render } from "../testing/render";
import type { Given } from "./plan";
import { plansUrl, VIEWER_PLAN } from "./plan";
import { type Give, STEER_PAUSE_MS, useGiveToPlayback, useSteering } from "./useSteering";

const RUN_ID = "climate_box-climate-0f00ba11";
const PLAYBACK = {
  scenario_id: "climate_box",
  run_id: RUN_ID,
  layout: "default",
  epoch: 0,
  greenhouse_id: "climate_box",
  started_at: "2026-03-01T00:00:00Z",
  simulated_now: "2026-03-01T06:00:00Z",
  time_s: 21_600,
  day: 0,
  playing: false,
  seconds_per_day: 10,
  worked_out_s: 86_400,
  every_s: 300,
  targets: [],
  commands: [],
  crop: [],
};

type Steering = ReturnType<typeof useSteering>;
let steering: Steering | null = null;
let played: PlaybackLoad[] = [];

function Steered({
  shown,
  fetchFn,
}: {
  shown: Readonly<Record<string, number>>;
  fetchFn: typeof fetch;
}) {
  const give = useGiveToPlayback("climate_box", (load) => played.push(load), fetchFn);
  steering = useSteering("climate_box", shown, give);
  return null;
}

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

/** A gateway that takes every plan given, and records what was asked of it. */
function gateway(accepted = true) {
  const given: unknown[] = [];
  const fetchFn = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/playback")) {
      return new Response(JSON.stringify(PLAYBACK));
    }
    if (url === `${plansUrl(RUN_ID)}/${VIEWER_PLAN}`) {
      return new Response("{}", { status: 404 });
    }
    given.push(JSON.parse(String(init?.body)));
    return new Response(
      JSON.stringify(accepted ? { accepted } : { accepted, errors: ["not authorised"] }),
    );
  });
  return { fetchFn: fetchFn as unknown as typeof fetch, given };
}

async function waited(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("a followed run steered from the panels", () => {
  afterEach(() => {
    vi.useRealTimers();
    steering = null;
    played = [];
  });

  it("gives the levels a drag set once it rests, as one revision, then reads the playback", async () => {
    vi.useFakeTimers();
    const { fetchFn, given } = gateway();
    render(<Steered shown={{ fan: 0 }} fetchFn={fetchFn} />);

    act(() => steering?.steer({ fan: 0.2 }));
    act(() => steering?.steer({ fan: 0.6 }));
    act(() => steering?.steer({ roof_vent: 1 }));
    await waited(STEER_PAUSE_MS - 1);
    expect(given).toEqual([]);
    expect(steering?.asked).toEqual({ fan: 0.6, roof_vent: 1 });

    await waited(1);
    expect(given).toHaveLength(1);
    expect(given[0]).toMatchObject({
      plan_id: VIEWER_PLAN,
      run_id: RUN_ID,
      revision: 1,
      actions: [
        { action: { kind: "set_level", device_id: "fan", level: 0.6 }, timing: { kind: "asap" } },
        { action: { kind: "set_level", device_id: "roof_vent", level: 1 } },
      ],
    });
    expect(played.at(-1)).toMatchObject({ status: "loaded", state: { runId: RUN_ID } });
    expect(steering?.refusal).toBeNull();
    expect(steering?.given).toBe(1);
  });

  it("shows a level as asked until the run has it", async () => {
    vi.useFakeTimers();
    const { fetchFn } = gateway();
    const shown = render(<Steered shown={{ fan: 0 }} fetchFn={fetchFn} />);

    act(() => steering?.steer({ fan: 0.6 }));
    await waited(STEER_PAUSE_MS);
    expect(steering?.asked).toEqual({ fan: 0.6 });

    shown.rerender(<Steered shown={{ fan: 0.6 }} fetchFn={fetchFn} />);
    expect(steering?.asked).toEqual({});
  });

  it("says why a change was refused, and stops showing what was refused", async () => {
    vi.useFakeTimers();
    const { fetchFn } = gateway(false);
    render(<Steered shown={{ fan: 0 }} fetchFn={fetchFn} />);

    act(() => steering?.steer({ fan: 0.6 }));
    await waited(STEER_PAUSE_MS);

    expect(steering?.refusal).toBe("not authorised");
    expect(steering?.asked).toEqual({});
  });

  it("gives targets at once", async () => {
    vi.useFakeTimers();
    const { fetchFn, given } = gateway();
    render(<Steered shown={{}} fetchFn={fetchFn} />);

    act(() => steering?.setTargets({ heating_day: 22 }));
    await waited(0);

    expect(given[0]).toMatchObject({
      actions: [{ action: { kind: "set_target", target: "heating_day", value_c: 22 } }],
    });
  });

  it("gives what is asked of a plant at once", async () => {
    vi.useFakeTimers();
    const { fetchFn, given } = gateway();
    render(<Steered shown={{}} fetchFn={fetchFn} />);

    act(() => steering?.act([{ kind: "lower", plant_id: "p30", by_internodes: 1 }]));
    await waited(0);

    expect(given[0]).toMatchObject({
      actions: [{ action: { kind: "lower", plant_id: "p30" }, timing: { kind: "asap" } }],
    });
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
