import { refusal } from "../builder/api";
import { contractCheck } from "../loadJson";
import { STORED_RUN_SCHEMA } from "../scene/generated/storedRunSchema";
import type { StoredRun } from "../scene/generated/storedRunTypes";

/** What a fork changes as it branches, as the simulator takes it: targets, by
 * name, in °C, from its next minute, or devices' levels from its instant. */
export type ForkChange =
  | { kind: "targets"; targets: Readonly<Record<string, number>> }
  | { kind: "levels"; levels: Readonly<Record<string, number>> };

/** A fork asked for (P17.8, decision 0065): the moment it branches at, the
 * layout it goes on in, if another, and what it changes there. */
export interface ForkAsked {
  timeS: number;
  layout?: string;
  changes?: readonly ForkChange[];
}

/** The fork started, or why it was not. */
export type ForkAnswer =
  | { status: "started"; runId: string; epoch: number }
  | { status: "unavailable"; reason: string };

const checkRun = contractCheck<StoredRun>(STORED_RUN_SCHEMA, "the run");

/** Asks for a fork of a stored epoch: a new epoch, computed by a worker, which
 * leaves the one it came from as it was. */
export async function forkEpoch(
  runId: string,
  epoch: number,
  asked: ForkAsked,
  fetchFn: typeof fetch = fetch,
): Promise<ForkAnswer> {
  const layout = asked.layout === undefined ? "" : `&layout=${encodeURIComponent(asked.layout)}`;
  const url = `/api/runs/${encodeURIComponent(runId)}/epochs/${epoch}/forks?t=${asked.timeS}${layout}`;
  try {
    const response = await fetchFn(url, {
      method: "POST",
      body: JSON.stringify(asked.changes ?? []),
    });
    if (!response.ok) {
      return { status: "unavailable", reason: await refusal(response) };
    }
    const checked = checkRun(await response.json());
    return checked.ok
      ? { status: "started", runId: checked.value.run_id, epoch: checked.value.epoch }
      : { status: "unavailable", reason: "the fork's answer is not what the viewer reads" };
  } catch {
    return { status: "unavailable", reason: "the simulator could not be reached" };
  }
}

/** Why no fork can be made at a moment of an epoch: at its end, nothing is left
 * to fork; `null` if one can. */
export function whyNoFork(position: { time_s: number; duration_s: number | null }): string | null {
  return position.duration_s !== null && position.time_s >= position.duration_s
    ? "The run ends here: go back to a moment to fork from."
    : null;
}
