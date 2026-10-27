import { useCallback, useEffect, useState } from "react";

import { contractCheck } from "../loadJson";
import { PLAYBACK_SCHEMA } from "./generated/playbackSchema";
import type { PlaybackState as ServedPlayback } from "./generated/playbackTypes";
import { layoutText } from "./moves";
import type { ScheduledCommand, TargetChange } from "./source";

// How often a view following a played-back run asks where its clock is.
const POLL_MS = 1000;
const MINUTE_S = 60;
const NOT_FOUND = 404;

/**
 * A scenario's own run played back against one clock (P10.2, decision
 * 0041), as the simulator says it stands: the run, its layout (its own, or
 * one rearranged, #271), its epoch, the instant its clock has reached and
 * that as seconds into the run, its day, whether it plays and how fast, and
 * how far ahead its records are worked out. A consumer reads the same run
 * by the same identity and clock.
 */
export interface PlaybackState {
  runId: string;
  /** Its layout, by the name a run knows it by: `default`, or one with
   * moves, `default~heater:-1.0:0.5`. */
  layout: string;
  epoch: number;
  /** The instant its run's clock started at. */
  startedAt: string;
  simulatedNow: string;
  timeS: number;
  day: number;
  playing: boolean;
  secondsPerDay: number;
  workedOutS: number;
  /** The target changes its epoch has made, from their moments on (#274,
   * decision 0043): a view following it asks for its run with them. */
  targets: TargetChange[];
  /** The levels its epoch's run has been given, of its equipment, doors and
   * vents, each from its moment on (P13.8): a view following it asks for
   * its run with them, as its commands. */
  commands: ScheduledCommand[];
}

export type PlaybackLoad =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unstarted" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; state: PlaybackState };

export type PlaybackCommand = "play" | "pause" | "restart";

export function playbackUrl(scenarioId: string): string {
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/playback`;
}

const checkPlayback = contractCheck<ServedPlayback>(PLAYBACK_SCHEMA, "the playback");

/** The playback's state as the simulator answers it, checked rather than
 * trusted; null if it is not one. */
export function parsePlayback(body: unknown): PlaybackState | null {
  const checked = checkPlayback(body);
  if (!checked.ok) {
    return null;
  }
  const played = checked.value;
  return {
    runId: played.run_id,
    layout: played.layout,
    epoch: played.epoch,
    startedAt: played.started_at,
    simulatedNow: played.simulated_now,
    timeS: played.time_s,
    day: played.day,
    playing: played.playing,
    secondsPerDay: played.seconds_per_day,
    workedOutS: played.worked_out_s,
    targets: played.targets.map(([timeS, target, valueC]) => ({ timeS, target, valueC })),
    commands: played.commands.map(([timeS, actuatorId, level]) => ({
      timeS,
      actuatorId,
      level,
    })),
  };
}

/** Where a playback stands, or why it cannot be said. */
export async function loadPlayback(
  scenarioId: string,
  fetchFn: typeof fetch = fetch,
  init: RequestInit = {},
): Promise<PlaybackLoad> {
  let response: Response;
  try {
    response = await fetchFn(playbackUrl(scenarioId), init);
  } catch (error) {
    if (init.signal?.aborted) {
      throw error;
    }
    return { status: "unavailable", reason: "the simulator could not be reached" };
  }
  if (response.status === NOT_FOUND) {
    return { status: "unstarted" };
  }
  return answered(response);
}

/** The playback's state a response says, or why it says none: its status,
 * or a body that is not the state, or not JSON at all. */
async function answered(response: Response): Promise<PlaybackLoad> {
  if (!response.ok) {
    return { status: "unavailable", reason: `the simulator answered ${response.status}` };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const state = parsePlayback(body);
  return state === null
    ? { status: "unavailable", reason: "the playback's state is not what the viewer reads" }
    : { status: "loaded", state };
}

/** Starts the scenario's playback, or tells it to play, pause or start over;
 * started over with a layout, it plays that layout's run from its start, a
 * new run (#271). */
export async function commandPlayback(
  scenarioId: string,
  command: PlaybackCommand | "start",
  fetchFn: typeof fetch = fetch,
  layout?: string,
): Promise<PlaybackLoad> {
  const query = layout === undefined ? "" : `?layout=${layoutText(layout)}`;
  let response: Response;
  try {
    response = await fetchFn(`${playbackUrl(scenarioId)}/${command}${query}`, { method: "POST" });
  } catch {
    return { status: "unavailable", reason: "the simulator could not be reached" };
  }
  return answered(response);
}

/** The playback's clock as a moment the viewer draws: its minute, as runs
 * are drawn on whole minutes. */
export function followedMoment(state: PlaybackState): number {
  return Math.floor(state.timeS / MINUTE_S) * MINUTE_S;
}

const NONE: PlaybackLoad = { status: "none" };
const LOADING: PlaybackLoad = { status: "loading" };

/**
 * Where the scenario's playback stands, asked every second while
 * `scenarioId` is followed, and kept as the playback of that scenario: a
 * view following another is never told the one before's clock, not even
 * on its first render. An answer that fails is said, and asked again.
 * The setter keeps a state given, as after a command, for the scenario
 * followed when it was made. Nothing is asked for when no scenario is
 * followed.
 */
export function usePlayback(
  scenarioId: string | null,
  fetchFn: typeof fetch = fetch,
): [PlaybackLoad, (load: PlaybackLoad) => void] {
  const [held, setHeld] = useState<{ scenarioId: string | null; load: PlaybackLoad }>({
    scenarioId: null,
    load: NONE,
  });
  useEffect(() => {
    if (scenarioId === null) {
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ask = async () => {
      let load: PlaybackLoad;
      try {
        load = await loadPlayback(scenarioId, fetchFn, { signal: controller.signal });
      } catch (error) {
        if (controller.signal.aborted) {
          return; // given up: the view no longer follows it
        }
        load = { status: "unavailable", reason: String(error) };
      }
      setHeld({ scenarioId, load });
      timer = setTimeout(ask, POLL_MS);
    };
    void ask();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [scenarioId, fetchFn]);
  const keep = useCallback((load: PlaybackLoad) => setHeld({ scenarioId, load }), [scenarioId]);
  const load = scenarioId === null ? NONE : held.scenarioId === scenarioId ? held.load : LOADING;
  return [load, keep];
}
