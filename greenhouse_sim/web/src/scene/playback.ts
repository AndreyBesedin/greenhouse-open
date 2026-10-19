import { useEffect, useState } from "react";

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
  if (!response.ok) {
    return { status: "unavailable", reason: `the simulator answered ${response.status}` };
  }
  const state = parsePlayback(await response.json());
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
  if (!response.ok) {
    return { status: "unavailable", reason: `the simulator answered ${response.status}` };
  }
  const state = parsePlayback(await response.json());
  return state === null
    ? { status: "unavailable", reason: "the playback's state is not what the viewer reads" }
    : { status: "loaded", state };
}

/** The playback's clock as a moment the viewer draws: its minute, as runs
 * are drawn on whole minutes. */
export function followedMoment(state: PlaybackState): number {
  return Math.floor(state.timeS / MINUTE_S) * MINUTE_S;
}

/**
 * Where the scenario's playback stands, asked every second while
 * `scenarioId` is followed; `refresh` asks again at once, as after a
 * command. Nothing is asked for when no scenario is followed.
 */
export function usePlayback(
  scenarioId: string | null,
  fetchFn: typeof fetch = fetch,
): [PlaybackLoad, (load: PlaybackLoad) => void] {
  const [load, setLoad] = useState<PlaybackLoad>({ status: "none" });
  useEffect(() => {
    if (scenarioId === null) {
      setLoad({ status: "none" });
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setLoad({ status: "loading" });
    const ask = async () => {
      try {
        const answered = await loadPlayback(scenarioId, fetchFn, { signal: controller.signal });
        setLoad(answered);
      } catch {
        return; // given up: the view no longer follows it
      }
      timer = setTimeout(ask, POLL_MS);
    };
    void ask();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [scenarioId, fetchFn]);
  return [load, setLoad];
}
