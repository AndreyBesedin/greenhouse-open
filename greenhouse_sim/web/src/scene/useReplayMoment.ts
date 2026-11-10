import { useEffect, useRef, useState } from "react";

import { DAY_S, dayEnd } from "../clock";
import { CLIMATE_FIELD, fieldUrl } from "../fields/source";
import { withTime } from "./edits";
import { scenarioRun } from "./run";
import type { SceneSource } from "./source";
import type { SetSource } from "./useSource";

const MINUTE_S = 60;
const HOUR_S = 3600;
const MS_PER_S = 1000;
// How long a climate field is taken to be on its way before one has been
// timed: a moment's grid run of an hour or two, measured at 1 to 5 s
// (P22.6).
export const FIRST_LATENCY_MS = 3000;
// How long a moment drawn takes to arrive once the position is there: its
// field asked again, which the simulator keeps, and the rest of the moment's
// parts, measured at 0.1 to 0.5 s (P22.6).
const DRAWN_AGAIN_MS = 500;
// How much older than it reads the position's moment may be: the replay asks
// where it stands every second (`useReplay`), so a day is ended that much
// sooner.
const POSITION_AGE_MS = 1000;

/** The moment a replay draws for a position's: its whole minute, as runs are
 * drawn on whole minutes. */
export function replayedMoment(timeS: number): number {
  return Math.floor(timeS / MINUTE_S) * MINUTE_S;
}

/** How a replay's position plays, while it does: its pace, and how far it can go. */
export interface PlayedPace {
  secondsPerDay: number;
  frontierS: number;
}

/** How long the fields asked for ahead took, the latest and the latest of a
 * day's first minute, which is a night's: null until one has been timed. */
export interface Latencies {
  latestMs: number;
  dayStartMs: number | null;
}

/**
 * The moment a playing replay asks for ahead of its position (P22.6): where
 * the position will stand once the field asked now arrives, if it takes as
 * long as the last one did, on the whole hour, whose field is a grid run of
 * an hour rather than up to two (`GRID_RUN_S`), and an hour on from the
 * moment drawn at least.
 *
 * The next day's first minute is asked for after that one, in time for the
 * position to find it there, so that the panels change day as the timeline
 * does: the last moment of a day is no later than leaves the time to ask for
 * it, once that one is drawn, and it is asked for itself once no other
 * moment leaves that time. A midnight is the day it ends, not the next.
 * Never past the frontier; null if that leaves nothing after the moment drawn.
 */
export function momentAhead({
  momentS,
  drawnS,
  latencies,
  pace,
}: {
  momentS: number;
  drawnS: number;
  latencies: Latencies;
  pace: PlayedPace;
}): number | null {
  const simulatedPerMs = DAY_S / pace.secondsPerDay / MS_PER_S;
  const onItsWayS = simulatedPerMs * latencies.latestMs;
  // How far the position goes from drawing a moment to having the next day's
  // first minute: its field asked again, then the first minute's, as late as
  // the position reads.
  const toTheDayS =
    simulatedPerMs *
    ((latencies.dayStartMs ?? latencies.latestMs) + DRAWN_AGAIN_MS + POSITION_AGE_MS);
  const nextHour = (Math.floor(drawnS / HOUR_S) + 1) * HOUR_S;
  const nextDayBegins = dayEnd(momentS) + MINUTE_S;
  const lastOfTheDay = Math.floor((nextDayBegins - MINUTE_S - toTheDayS) / HOUR_S) * HOUR_S;
  const ahead =
    momentS + onItsWayS + toTheDayS >= nextDayBegins || lastOfTheDay < nextHour
      ? nextDayBegins
      : Math.min(
          Math.max(Math.round((momentS + onItsWayS) / HOUR_S) * HOUR_S, nextHour),
          lastOfTheDay,
        );
  const reachable = Math.min(ahead, replayedMoment(pace.frontierS));
  return reachable > drawnS ? reachable : null;
}

/** A moment asked for ahead, and whether the simulator has answered it. */
interface Ahead {
  momentS: number;
  answered: boolean;
}

/**
 * The moment a replay's position stands at (P17.6) as the moment drawn: moved
 * on once the moment asked for before has arrived, so that a position that
 * moves faster than the simulator answers is never drawn half over; a moment
 * whose field failed has arrived as far as it will, and the view moves on.
 * Only the climate field is asked for a moment (`fieldUrl`): any other field
 * the view draws is the layout's and says no moment, so nothing is waited for
 * and the replay is never held by it.
 *
 * While the position plays over the climate field (`pace`), the field is asked
 * for ahead (`momentAhead`), one moment at a time, with the field drawn kept
 * on show; the moment is drawn once the simulator has answered and the
 * position has reached it, when the simulator has its grid run and answers
 * it, and the glazing and openings that wait on that run, at once (P22.6).
 * The position going back, or no longer playing, leaves the moment ahead.
 */
export function useReplayMoment({
  momentS,
  pace = null,
  source,
  setSource,
  field,
  fieldShownMoment,
  fieldFailed,
  fetchFn = fetch,
}: {
  /** The position's moment, or null while there is none. */
  momentS: number | null;
  /** How the position plays, or null while it does not. */
  pace?: PlayedPace | null;
  source: SceneSource;
  setSource: (change: SetSource) => void;
  /** The field drawn over the scene, by name, or null for none. */
  field: string | null;
  fieldShownMoment: number | null;
  fieldFailed: boolean;
  fetchFn?: typeof fetch;
}) {
  const waitsForField = field === CLIMATE_FIELD;
  const asked = source.kind === "scenario" ? (source.time ?? 0) : null;
  const arrived = !waitsForField || fieldShownMoment === asked || fieldFailed;
  const [ahead, setAhead] = useState<Ahead | null>(null);
  const latencies = useRef<Latencies>({ latestMs: FIRST_LATENCY_MS, dayStartMs: null });
  // The source the moment ahead is asked of, read when it is asked, not a
  // reason to ask again: its moment is what changes as the replay plays.
  const sourceNow = useRef(source);
  sourceNow.current = source;
  const goesAhead = pace !== null && waitsForField && momentS !== null && asked !== null;
  const aheadS =
    goesAhead && ahead === null && arrived
      ? momentAhead({ momentS, drawnS: asked, latencies: latencies.current, pace })
      : null;

  // The moment ahead is let go once the position goes back before the moment
  // drawn, or stops playing.
  const behind = momentS !== null && asked !== null && momentS < asked;
  useEffect(() => {
    if (!goesAhead || behind) {
      setAhead(null);
    }
  }, [goesAhead, behind]);

  useEffect(() => {
    if (aheadS !== null) {
      setAhead({ momentS: aheadS, answered: false });
    }
  }, [aheadS]);

  const askedAheadS = ahead?.momentS ?? null;
  useEffect(() => {
    const asking = sourceNow.current;
    if (askedAheadS === null || asking.kind !== "scenario") {
      return;
    }
    const wanted = new AbortController();
    const started = performance.now();
    const answered = () => {
      if (!wanted.signal.aborted) {
        const tookMs = performance.now() - started;
        const dayStart = askedAheadS % DAY_S === MINUTE_S;
        latencies.current = {
          latestMs: tookMs,
          dayStartMs: dayStart ? tookMs : latencies.current.dayStartMs,
        };
        setAhead((now) => (now?.momentS === askedAheadS ? { ...now, answered: true } : now));
      }
    };
    const url = fieldUrl(
      asking.scenarioId,
      CLIMATE_FIELD,
      scenarioRun(withTime(asking, askedAheadS)),
    );
    // Read and let go: the field is drawn from the simulator's answer to the
    // same moment, asked again once the position is there. A failure is the
    // drawn field's to say, so it too is drawn when the position is there.
    void fetchFn(url, { signal: wanted.signal })
      .then((response) => response.arrayBuffer())
      .then(answered, answered);
    return () => wanted.abort();
  }, [askedAheadS, fetchFn]);

  const drawnAheadS =
    ahead?.answered === true && momentS !== null && momentS >= ahead.momentS ? ahead.momentS : null;
  useEffect(() => {
    if (drawnAheadS === null) {
      return;
    }
    setAhead(null);
    setSource((current) =>
      current.kind === "scenario" ? withTime(current, drawnAheadS) : current,
    );
  }, [drawnAheadS, setSource]);

  // Otherwise, the position's own moment, once the one asked before has arrived.
  const followsPosition = !goesAhead || behind || (ahead === null && aheadS === null);
  useEffect(() => {
    if (!followsPosition || momentS === null || asked === null || momentS === asked || !arrived) {
      return;
    }
    setSource((current) => (current.kind === "scenario" ? withTime(current, momentS) : current));
  }, [followsPosition, momentS, asked, arrived, setSource]);
}
