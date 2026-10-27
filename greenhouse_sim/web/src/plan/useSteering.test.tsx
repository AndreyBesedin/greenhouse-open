// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlaybackLoad } from "../scene/playback";
import { render } from "../testing/render";
import { plansUrl, VIEWER_PLAN } from "./plan";
import { STEER_PAUSE_MS, useSteering } from "./useSteering";

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
  steering = useSteering("climate_box", shown, (load) => played.push(load), fetchFn);
  return null;
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
});
