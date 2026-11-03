// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type Rendered, render } from "../testing/render";
import type { SceneSource } from "./source";
import { useFollow } from "./useFollow";
import type { SetSource } from "./useSource";

const ASKED_S = 3600;
const CLOCK_S = 7200;

/** The playback's answer, with its clock past the moment the view asked for. */
function playing(): Response {
  return new Response(
    JSON.stringify({
      scenario_id: "climate_box",
      run_id: "a-run",
      layout: "default",
      epoch: 0,
      greenhouse_id: "climate_box",
      started_at: "2026-03-01T00:00:00Z",
      simulated_now: "2026-03-01T00:00:00Z",
      time_s: CLOCK_S,
      day: 0,
      playing: true,
      seconds_per_day: 10,
      worked_out_s: 86_400,
      every_s: 300,
      targets: [],
      commands: [],
      crop: [],
    }),
  );
}

interface Drawn {
  field: string | null;
  fieldShownMoment: number | null;
  fieldFailed?: boolean;
}

describe("the moment a followed run draws, against what the field shows", () => {
  let rendered: Rendered | undefined;
  afterEach(() => {
    rendered?.unmount();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  /** A view following the run at the moment asked for, once the playback has
   * said where its clock stands; `moved` is whether the clock moved it on, and
   * `made` the source the changes make of the one drawn. */
  async function followed({ field, fieldShownMoment, fieldFailed = false }: Drawn) {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => playing()),
    );
    const source: SceneSource = {
      kind: "scenario",
      scenarioId: "climate_box",
      follow: true,
      time: ASKED_S,
      ...(field === null ? {} : { field }),
    };
    const setSource = vi.fn<(change: SetSource) => void>();
    const onClockMoved = vi.fn();
    function Probe() {
      useFollow({
        source,
        addressed: source,
        setSource,
        field,
        fieldShownMoment,
        fieldFailed,
        onClockMoved,
      });
      return null;
    }
    rendered = render(<Probe />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const made = setSource.mock.calls.reduce<SceneSource>(
      (current, [change]) => (typeof change === "function" ? change(current) : change),
      source,
    );
    return { moved: onClockMoved.mock.calls.length > 0, made };
  }

  it("waits for the climate field to show the moment asked for", async () => {
    const waiting = await followed({ field: "climate", fieldShownMoment: 0 });

    expect(waiting.moved).toBe(false);
    expect(waiting.made).toMatchObject({ time: ASKED_S });
  });

  it("moves on once the climate field shows it, or has failed to", async () => {
    const arrived = await followed({ field: "climate", fieldShownMoment: ASKED_S });
    expect(arrived.moved).toBe(true);
    expect(arrived.made).toMatchObject({ time: CLOCK_S });
    rendered?.unmount();

    const failed = await followed({ field: "climate", fieldShownMoment: 0, fieldFailed: true });
    expect(failed.moved).toBe(true);
    expect(failed.made).toMatchObject({ time: CLOCK_S });
  });

  it("is not held by a field that is not the climate's, which says no moment", async () => {
    // A prescribed field or the shear is the layout's, drawn at its time 0
    // whatever the moment: waiting for its moment would wait for ever.
    for (const field of ["shear", "uniform"]) {
      const held = await followed({ field, fieldShownMoment: 0 });

      expect(held.moved).toBe(true);
      expect(held.made).toMatchObject({ time: CLOCK_S });
      rendered?.unmount();
    }
  });

  it("moves on with no field drawn", async () => {
    const bare = await followed({ field: null, fieldShownMoment: null });

    expect(bare.moved).toBe(true);
    expect(bare.made).toMatchObject({ time: CLOCK_S });
  });
});
