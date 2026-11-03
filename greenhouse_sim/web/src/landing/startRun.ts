import { type Answered, refusal } from "../builder/api";
import { type PlaybackState, parsePlayback } from "../scene/playback";

/** The pace a run is started at unless another is asked for, in real seconds
 * for a simulated day. */
export const DEFAULT_PACE_S = 10;

/** A run of a scenario started at its own seed, as the runs dialog starts
 * one: the state of the playback that computes it, or why it was refused. */
export async function startRun(
  scenarioId: string,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<PlaybackState>> {
  const query = new URLSearchParams({ seconds_per_day: String(DEFAULT_PACE_S), seed: "default" });
  const url = `/api/scenarios/${encodeURIComponent(scenarioId)}/playback/start?${query}`;
  try {
    const response = await fetchFn(url, { method: "POST" });
    if (!response.ok) {
      return { ok: false, problem: await refusal(response) };
    }
    const state = parsePlayback(await response.json());
    return state === null
      ? { ok: false, problem: "the simulator's answer is not the playback's state" }
      : { ok: true, value: state };
  } catch (error) {
    return { ok: false, problem: error instanceof Error ? error.message : String(error) };
  }
}
