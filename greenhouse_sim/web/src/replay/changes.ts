import { useCallback } from "react";

import { refusal } from "../builder/api";
import { contractCheck } from "../loadJson";
import type { Action } from "../plan/generated/planTypes";
import type { Given } from "../plan/plan";
import type { ForkChange } from "./fork";
import { CHANGE_ASKED_SCHEMA } from "./generated/changeAskedSchema";
import type { ChangeAsked } from "./generated/changeAskedTypes";
import { EPOCH_CHANGES_SCHEMA } from "./generated/epochChangesSchema";
import type { EpochChanges, Status } from "./generated/epochChangesTypes";
import { epochUrl } from "./position";

export type { EpochChanges };

/**
 * A running epoch steered from its replay (P22.1, decision 0073): a target or a
 * level set in the panels is asked of the epoch through the store (P17.8,
 * `POST …/changes`), which its worker takes between its moments, logs and acts
 * on at its own clock, the next minute for a target. So a change asked is not
 * yet one given: the page reads the epoch's changes (`GET …/changes`) until the
 * worker has logged the request, at the moment it takes effect, or refused it,
 * or the epoch has ended without taking it.
 */

// How often the epoch's changes are read while a request waits for its worker:
// a paced worker looks every 50 ms, a free one once a day of its own.
export const LOOK_MS = 1000;
// How many reads in a row may fail before the page stops waiting and says so.
const LOOKS_UNANSWERED = 5;

/** Whether an epoch takes changes: one a worker works, or will. Any other has
 * ended, and a change of it is a fork from a moment of it. */
export function takesChanges(status: Status): boolean {
  return status === "queued" || status === "running";
}

/** What became of a request asked of an epoch, as its changes say. */
export type Taken =
  | { status: "taken"; atS: number }
  | { status: "refused"; reason: string }
  | { status: "waiting" };

/** What the epoch's changes say of `request`: taken, at the instant it takes
 * effect, once its worker has logged it and is done with it; refused, in the
 * worker's words, which a change logged and then refused is too; waiting, also
 * while it is logged and not yet done with, since a worker logs a change before
 * it acts on it and may refuse it then; or never to be taken, its epoch having
 * ended first. An epoch that ended with it logged and never done with, as a
 * crash leaves one, took it, as far as anything says. */
export function whatBecameOf(changes: EpochChanges, request: string): Taken {
  const refused = changes.refused.find((answer) => answer.request === request);
  if (refused !== undefined) {
    return { status: "refused", reason: refused.reason };
  }
  const logged = changes.log.find((entry) => entry.request === request);
  const running = takesChanges(changes.status);
  if (logged !== undefined && (changes.done.includes(request) || !running)) {
    return { status: "taken", atS: logged.at_s };
  }
  return running
    ? { status: "waiting" }
    : {
        status: "refused",
        reason: `the run was ${changes.status} before it took the change; a fork acts from a moment of it`,
      };
}

/** The changes a replay asks for the actions the panels set: levels together,
 * targets together. None for an action an epoch is not asked through its
 * replay, such as a plant's work, which only the viewer's own play offers, or
 * a device handed back to its controller. */
export function changesFor(actions: readonly Action[]): ForkChange[] | null {
  const levels: Record<string, number> = {};
  const targets: Record<string, number> = {};
  for (const action of actions) {
    if (action.kind === "set_level" && action.level !== "auto") {
      levels[action.device_id] = action.level;
    } else if (action.kind === "set_target") {
      targets[action.target] = action.value_c;
    } else {
      return null;
    }
  }
  return [
    ...(Object.keys(levels).length === 0 ? [] : [{ kind: "levels" as const, levels }]),
    ...(Object.keys(targets).length === 0 ? [] : [{ kind: "targets" as const, targets }]),
  ];
}

const checkAsked = contractCheck<ChangeAsked>(CHANGE_ASKED_SCHEMA, "the change asked");
const checkChanges = contractCheck<EpochChanges>(EPOCH_CHANGES_SCHEMA, "the epoch's changes");

function changesUrl(runId: string, epoch: number): string {
  return `${epochUrl(runId, epoch)}/changes`;
}

/** Asks a change of an epoch: the request its worker will know it by, or why
 * the simulator refused it, as for an epoch that has ended. */
export async function askOfEpoch(
  runId: string,
  epoch: number,
  change: ForkChange,
  fetchFn: typeof fetch = fetch,
): Promise<{ status: "asked"; request: string } | { status: "refused"; reason: string }> {
  try {
    const response = await fetchFn(changesUrl(runId, epoch), {
      method: "POST",
      body: JSON.stringify(change),
    });
    if (!response.ok) {
      return { status: "refused", reason: await refusal(response) };
    }
    const checked = checkAsked(await response.json());
    return checked.ok
      ? { status: "asked", request: checked.value.request }
      : { status: "refused", reason: "the simulator's answer is not what the viewer reads" };
  } catch {
    return { status: "refused", reason: "the simulator could not be reached" };
  }
}

/** The changes asked of an epoch and what became of them, or null if they could
 * not be read just then. */
export async function loadChanges(
  runId: string,
  epoch: number,
  fetchFn: typeof fetch = fetch,
): Promise<EpochChanges | null> {
  try {
    const response = await fetchFn(changesUrl(runId, epoch));
    if (!response.ok) {
      return null;
    }
    const checked = checkChanges(await response.json());
    return checked.ok ? checked.value : null;
  } catch {
    return null;
  }
}

function waited(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Waits for the epoch's worker to take a request: the moment it took effect
 * from, or why it was not. */
async function taken(
  runId: string,
  epoch: number,
  request: string,
  fetchFn: typeof fetch,
): Promise<Exclude<Taken, { status: "waiting" }>> {
  let unanswered = 0;
  for (;;) {
    const changes = await loadChanges(runId, epoch, fetchFn);
    if (changes === null) {
      unanswered += 1;
      if (unanswered >= LOOKS_UNANSWERED) {
        return {
          status: "refused",
          reason: "the simulator could not be reached to say whether the run took the change",
        };
      }
    } else {
      unanswered = 0;
      const became = whatBecameOf(changes, request);
      if (became.status !== "waiting") {
        return became;
      }
    }
    await waited(LOOK_MS);
  }
}

/**
 * Gives actions to a running epoch, as its replay's panels set them: asked of
 * it, then waited for until its worker has taken each. Given, it says the
 * moment the latest took effect from; refused, the first reason.
 */
export async function giveToEpoch(
  runId: string,
  epoch: number,
  actions: readonly Action[],
  fetchFn: typeof fetch = fetch,
): Promise<Given> {
  const changes = changesFor(actions);
  if (changes === null) {
    return { status: "refused", reason: "a replay steers a run's levels and targets only" };
  }
  let atS: number | undefined;
  for (const change of changes) {
    const asked = await askOfEpoch(runId, epoch, change, fetchFn);
    if (asked.status === "refused") {
      return asked;
    }
    const became = await taken(runId, epoch, asked.request, fetchFn);
    if (became.status === "refused") {
      return became;
    }
    atS = Math.max(atS ?? became.atS, became.atS);
  }
  return atS === undefined ? { status: "given" } : { status: "given", atS };
}

/** The epoch a replay steers, for `useSteering` and the panels: named by its
 * run and number alone, whether or not it is still computed, so that what
 * became of a change given it before it ended is still said after; and whether
 * it is computed, which decides whether a change made now steers it or forks it. */
export interface SteeredEpoch {
  epoch: string;
  give: (actions: Action[]) => Promise<Given>;
  computing: boolean;
}

export function steeredEpoch(
  runId: string,
  epoch: number,
  give: (actions: Action[]) => Promise<Given>,
  status: Status,
): SteeredEpoch {
  return { epoch: `${runId}#${epoch}`, give, computing: takesChanges(status) };
}

/** Whether a replay says how the changes given its epoch stand: while it is
 * computed, and after, while one is on its way or what became of one is said. */
export function saysSteering(
  computing: boolean,
  { waiting, taken, refusal }: { waiting: number; taken: number | null; refusal: string | null },
): boolean {
  return computing || waiting > 0 || taken !== null || refusal !== null;
}

/** How a replay's panels give actions to the epoch it shows, for `useSteering`. */
export function useGiveToEpoch(
  runId: string,
  epoch: number,
  fetchFn: typeof fetch = fetch,
): (actions: Action[]) => Promise<Given> {
  return useCallback(
    (actions: Action[]) => giveToEpoch(runId, epoch, actions, fetchFn),
    [runId, epoch, fetchFn],
  );
}
