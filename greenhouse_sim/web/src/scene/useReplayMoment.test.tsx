// @vitest-environment jsdom
import { act, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type Rendered, render } from "../testing/render";
import { renderHook } from "../testing/renderHook";
import type { SceneSource } from "./source";
import {
  FIRST_LATENCY_MS,
  type Latencies,
  momentAhead,
  type PlayedPace,
  replayedMoment,
  useReplayMoment,
} from "./useReplayMoment";
import type { SetSource } from "./useSource";

const SOURCE: SceneSource = { kind: "scenario", scenarioId: "climate_box", field: "climate" };

interface Props {
  momentS: number | null;
  source?: SceneSource;
  field?: string | null;
  fieldShownMoment?: number | null;
  fieldFailed?: boolean;
}

describe("the moment a replay draws", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function Probe(props: Props & { setSource: (change: SetSource) => void }) {
    useReplayMoment({
      momentS: props.momentS,
      source: props.source ?? SOURCE,
      setSource: props.setSource,
      field: props.field ?? null,
      fieldShownMoment: props.fieldShownMoment ?? null,
      fieldFailed: props.fieldFailed ?? false,
    });
    return null;
  }

  function shown(props: Props) {
    const setSource = vi.fn();
    rendered = render(<Probe {...props} setSource={setSource} />);
    /** The source the last change makes of the one drawn. */
    const made = (): SceneSource | undefined => {
      const change = setSource.mock.calls.at(-1)?.[0] as SetSource | undefined;
      return typeof change === "function" ? change(props.source ?? SOURCE) : change;
    };
    return { setSource, made, props };
  }

  it("is a whole minute", () => {
    expect(replayedMoment(3601)).toBe(3600);
    expect(replayedMoment(59.9)).toBe(0);
  });

  it("draws the position's moment", () => {
    const { made } = shown({ momentS: 7200 });

    expect(made()).toMatchObject({ kind: "scenario", time: 7200 });
  });

  it("does nothing while there is no position, or the moment is already drawn", () => {
    expect(shown({ momentS: null }).setSource).not.toHaveBeenCalled();
    rendered?.unmount();
    const drawn: SceneSource = { ...SOURCE, time: 7200 } as SceneSource;
    expect(shown({ momentS: 7200, source: drawn }).setSource).not.toHaveBeenCalled();
  });

  it("waits for the field of the moment asked for before moving on", () => {
    const waiting = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      field: "climate",
      fieldShownMoment: 0,
    });
    expect(waiting.setSource).not.toHaveBeenCalled();
    rendered?.unmount();

    const arrived = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      field: "climate",
      fieldShownMoment: 3600,
    });
    expect(arrived.setSource).toHaveBeenCalledOnce();
  });

  it("moves on when the field of the moment asked for failed, as it will not arrive", () => {
    const failed = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      field: "climate",
      fieldShownMoment: 0,
      fieldFailed: true,
    });

    expect(failed.setSource).toHaveBeenCalledOnce();
  });

  it("is not held by a field that is not the climate's, which says no moment", () => {
    // A prescribed field or the shear is the layout's, drawn at its time 0
    // whatever the moment: waiting for its moment would wait for ever.
    for (const field of ["shear", "prescribed"]) {
      const held = shown({
        momentS: 7200,
        source: { ...SOURCE, field, time: 3600 } as SceneSource,
        field,
        fieldShownMoment: 0,
      });

      expect(held.setSource).toHaveBeenCalledOnce();
      rendered?.unmount();
    }
  });

  it("changes only a scenario's source", () => {
    const { setSource } = shown({ momentS: 60, source: { kind: "example" } });

    expect(setSource).not.toHaveBeenCalled();
  });
});

const HOUR = 3600;
const DAY = 86_400;
// A moment of a run by its day, counted from 1, and its time of day.
const at = (day: number, hours: number, minutes = 0) =>
  (day - 1) * DAY + hours * HOUR + minutes * 60;
// Ten seconds a day, as far as the run goes: a second of play is 2.4 h.
const TEN_S_A_DAY: PlayedPace = { secondsPerDay: 10, frontierS: 120 * DAY };
// Fields that take 3 s, a day's first minute's not yet timed: 7.2 h on its way,
// and 10.8 h from a moment drawn to the next day's first minute.
const SLOW: Latencies = { latestMs: 3000, dayStartMs: null };

describe("the moment a playing replay asks for ahead", () => {
  it("is where the position will be when the answer arrives, on the whole hour", () => {
    // Three seconds on at ten seconds a day is 7.2 h: 13:12, so 13:00.
    expect(
      momentAhead({
        momentS: at(3, 6),
        drawnS: at(3, 5),
        latencies: SLOW,
        pace: TEN_S_A_DAY,
      }),
    ).toBe(at(3, 13));
  });

  it("is an hour on from the moment drawn at least, however slowly it plays", () => {
    const slow: PlayedPace = { secondsPerDay: 60, frontierS: 120 * DAY };

    expect(
      momentAhead({
        momentS: at(3, 6),
        drawnS: at(3, 6),
        latencies: { latestMs: 1000, dayStartMs: null },
        pace: slow,
      }),
    ).toBe(at(3, 7));
  });

  it("is the next day's first minute, once no other moment leaves the time to ask for it", () => {
    // 15:00 and 7.2 h on is 22:12, and the day ends before another 10.8 h.
    expect(
      momentAhead({ momentS: at(3, 15), drawnS: at(3, 14), latencies: SLOW, pace: TEN_S_A_DAY }),
    ).toBe(at(4, 0, 1));
  });

  it("ends a day no later than leaves the time for the next day's first minute", () => {
    // A first minute timed at 1 s is 6 h from a moment drawn, with the position
    // read a second late: 18:00 at the latest.
    const timed: Latencies = { latestMs: 3000, dayStartMs: 1000 };
    const from = (momentS: number) =>
      momentAhead({ momentS, drawnS: at(3, 9), latencies: timed, pace: TEN_S_A_DAY });

    expect(from(at(3, 10))).toBe(at(3, 17));
    expect(from(at(3, 10, 45))).toBe(at(3, 18));
    expect(from(at(3, 11))).toBe(at(4, 0, 1));
  });

  it("is the next day's first minute, once the answer would arrive in it", () => {
    // 22:00 and 7.2 h on is 05:12 of the next day: its first minute is asked.
    expect(
      momentAhead({ momentS: at(3, 22), drawnS: at(3, 21), latencies: SLOW, pace: TEN_S_A_DAY }),
    ).toBe(at(4, 0, 1));
  });

  it("is never a midnight, which is the day it ends': the next day's first minute", () => {
    // 16:48 and 7.2 h on is midnight exactly.
    const ahead = momentAhead({
      momentS: at(3, 16, 48),
      drawnS: at(3, 16),
      latencies: SLOW,
      pace: TEN_S_A_DAY,
    });

    expect(ahead).toBe(at(4, 0, 1));
  });

  it("is the hour, not the day's first minute, once the position is in that day", () => {
    expect(
      momentAhead({ momentS: at(4, 1), drawnS: at(3, 21), latencies: SLOW, pace: TEN_S_A_DAY }),
    ).toBe(at(4, 8));
  });

  it("starts no day on the run's first, which the moment drawn is in", () => {
    expect(momentAhead({ momentS: 0, drawnS: 0, latencies: SLOW, pace: TEN_S_A_DAY })).toBe(
      at(1, 7),
    );
  });

  it("is not past the frontier, and is none once that leaves nothing after the moment drawn", () => {
    const computing: PlayedPace = { secondsPerDay: 10, frontierS: at(3, 8, 30) + 15 };

    expect(
      momentAhead({ momentS: at(3, 6), drawnS: at(3, 5), latencies: SLOW, pace: computing }),
    ).toBe(at(3, 8, 30));
    expect(
      momentAhead({
        momentS: at(3, 8, 30),
        drawnS: at(3, 8, 30),
        latencies: SLOW,
        pace: computing,
      }),
    ).toBeNull();
  });
});

describe("a playing replay's moment, asked for ahead", () => {
  interface Played {
    momentS: number;
    fieldShownMoment: number;
    pace: PlayedPace | null;
  }
  const START: Played = { momentS: at(3, 6), fieldShownMoment: at(3, 5), pace: TEN_S_A_DAY };

  /** A replay drawn at 05:00 of its third day, its source the hook's to change. */
  function played() {
    const answers: (() => void)[] = [];
    const fetchFn = vi.fn(
      (_url: string, _init?: RequestInit) =>
        new Promise<Response>((resolve) => {
          answers.push(() => resolve(new Response("{}")));
        }),
    );
    const hook = renderHook((props: Played) => {
      const [source, setSource] = useState<SceneSource>({
        ...SOURCE,
        time: at(3, 5),
      } as SceneSource);
      useReplayMoment({
        ...props,
        source,
        setSource,
        field: "climate",
        fieldFailed: false,
        fetchFn: fetchFn as unknown as typeof fetch,
      });
      return source.kind === "scenario" ? source.time : undefined;
    }, START);
    /** The moments of the climate fields asked for ahead, in seconds. */
    const askedAhead = () =>
      fetchFn.mock.calls.map(([url]) =>
        Number(new URL(url, "http://viewer").searchParams.get("t")),
      );
    const answer = async () => {
      await act(async () => {
        for (const give of answers.splice(0)) {
          give();
        }
      });
    };
    return { hook, fetchFn, askedAhead, answer };
  }

  it("asks for the field ahead, keeps the one drawn, and draws it once the position is there", async () => {
    const replay = played();
    // Not yet timed, the field is taken to come in FIRST_LATENCY_MS: 7.2 h on.
    expect(FIRST_LATENCY_MS).toBe(3000);
    expect(replay.askedAhead()).toEqual([at(3, 13)]);

    // The position moves on before the answer, and after it, short of the moment.
    replay.hook.rerender({ ...START, momentS: at(3, 9) });
    await replay.answer();
    replay.hook.rerender({ ...START, momentS: at(3, 12) });
    expect(replay.hook.current).toBe(at(3, 5));
    expect(replay.fetchFn).toHaveBeenCalledOnce();

    replay.hook.rerender({ ...START, momentS: at(3, 13, 10) });
    expect(replay.hook.current).toBe(at(3, 13));
  });

  it("asks for the next moment only once the one drawn has arrived", async () => {
    const replay = played();
    await replay.answer();
    replay.hook.rerender({ ...START, momentS: at(3, 14) });
    expect(replay.hook.current).toBe(at(3, 13));
    // Drawn at 13:00, its field still on its way: nothing more is asked.
    replay.hook.rerender({ ...START, momentS: at(3, 15) });
    expect(replay.fetchFn).toHaveBeenCalledOnce();

    replay.hook.rerender({ ...START, momentS: at(3, 15), fieldShownMoment: at(3, 13) });
    expect(replay.fetchFn).toHaveBeenCalledTimes(2);
  });

  it("lets the moment ahead go, and draws the position's, when it goes back or stops playing", () => {
    const back = played();
    const asked = back.fetchFn.mock.calls[0]?.[1]?.signal;
    back.hook.rerender({ ...START, momentS: at(2, 12) });

    expect(asked?.aborted).toBe(true);
    expect(back.hook.current).toBe(at(2, 12));
    back.hook.unmount();

    const paused = played();
    paused.hook.rerender({ ...START, pace: null });
    expect(paused.hook.current).toBe(at(3, 6));
    paused.hook.unmount();
  });
});
