import { useCallback, useEffect, useState } from "react";

// How often a view following a played-back run asks where its clock is.
const POLL_MS = 1000;
const MINUTE_S = 60;
const NOT_FOUND = 404;

/**
 * A scenario's own run played back against one clock (P10.2, decision
 * 0041), as the simulator says it stands: the run, its epoch, the instant
 * its clock has reached and that as seconds into the run, its day, whether
 * it plays and how fast, and how far ahead its records are worked out. A
 * consumer reads the same run by the same identity and clock.
 */
export interface PlaybackState {
  runId: string;
  epoch: number;
  simulatedNow: string;
  timeS: number;
  day: number;
  playing: boolean;
  secondsPerDay: number;
  workedOutS: number;
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

/** The playback's state as the simulator answers it, checked rather than
 * trusted; null if it is not one. */
export function parsePlayback(body: unknown): PlaybackState | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const b = body as Record<string, unknown>;
  const numbers = ["epoch", "time_s", "day", "seconds_per_day", "worked_out_s"] as const;
  if (
    typeof b.run_id !== "string" ||
    typeof b.simulated_now !== "string" ||
    typeof b.playing !== "boolean" ||
    numbers.some((name) => typeof b[name] !== "number")
  ) {
    return null;
  }
  return {
    runId: b.run_id,
    epoch: b.epoch as number,
    simulatedNow: b.simulated_now,
    timeS: b.time_s as number,
    day: b.day as number,
    playing: b.playing,
    secondsPerDay: b.seconds_per_day as number,
    workedOutS: b.worked_out_s as number,
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

/** Starts the scenario's playback, or tells it to play, pause or start over. */
export async function commandPlayback(
  scenarioId: string,
  command: PlaybackCommand | "start",
  fetchFn: typeof fetch = fetch,
): Promise<PlaybackLoad> {
  let response: Response;
  try {
    response = await fetchFn(`${playbackUrl(scenarioId)}/${command}`, { method: "POST" });
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
