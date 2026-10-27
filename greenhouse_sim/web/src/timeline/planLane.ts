import { contractCheck } from "../loadJson";
import { ACTION_STATE_SCHEMA } from "../plan/generated/actionStateSchema";
import type { ActionRef, ActionState, ActionStateKind } from "../plan/generated/actionStateTypes";
import { OUTCOME_BATCH_SCHEMA } from "../plan/generated/outcomeBatchSchema";
import type {
  ActionOutcome,
  OutcomeBatch,
  OutcomeStatus,
} from "../plan/generated/outcomeBatchTypes";
import type { Action, Harvest } from "../plan/generated/planTypes";

/**
 * The plan lane of a run followed as it plays (P13.8): what its plans had
 * due, what became of each and why, as its outcome log says it through the
 * consumer interface (`/consumer/v1`), and what is still to come, as its
 * gateway lists it (`/actuation/v1`). Each is placed at its moment, in
 * seconds into the run, as the timeline places its events: an outcome where
 * its action started, or was resolved without starting; an action still to
 * come where it falls due.
 */
export interface PlanEntry {
  /** Its moment, in seconds into the run; null for an action still to come
   * as soon as it can, which has none yet. */
  timeS: number | null;
  planId: string;
  /** Which action, as people spell it: `change_1`, `tick@3`. */
  ref: string;
  /** What it does, in words. */
  action: string;
  /** What became of it, or, still to come, how it stands. */
  status: OutcomeStatus | ActionStateKind;
  reason: string | null;
  resolved: boolean;
}

export type PlanLaneState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; entries: PlanEntry[] };

/** The run whose plan lane is drawn: its identifier, its epoch, and the
 * instant its clock started at; and how many times the viewer has given it
 * a plan (`version`), so that the lane is read again after each, even at a
 * clock that does not move, as a paused run's does not. */
export interface PlanLaneRun {
  runId: string;
  epoch: number;
  startedAt: string;
  version?: number;
}

/** What carried an action out, of the outcomes. */
export const RAN: ReadonlySet<string> = new Set(["executed", "late"]);

// How many pages of outcomes are read at most: a run's whole log, many
// times over what its plans hold.
const MOST_PAGES = 50;

const checkBatch = contractCheck<OutcomeBatch>(OUTCOME_BATCH_SCHEMA, "the outcomes");
const checkState = contractCheck<ActionState>(ACTION_STATE_SCHEMA, "an action");

/** A run's plan lane: every outcome its log holds by its clock, and every
 * action still to come; every failure becomes a state. */
export async function loadPlanLane(
  run: PlanLaneRun,
  fetchFn: typeof fetch = fetch,
): Promise<PlanLaneState> {
  try {
    const outcomes = await allOutcomes(run.runId, fetchFn);
    const toCome = await actionsToCome(run.runId, fetchFn);
    return {
      status: "loaded",
      entries: [
        ...outcomes.map((outcome) => resolvedEntry(outcome, run.startedAt)),
        ...toCome.map((state) => comingEntry(state, run.startedAt)),
      ],
    };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

async function allOutcomes(runId: string, fetchFn: typeof fetch): Promise<ActionOutcome[]> {
  const outcomes: ActionOutcome[] = [];
  let after = 0;
  for (let page = 0; page < MOST_PAGES; page += 1) {
    const batch = checked(
      await read(`/consumer/v1/runs/${encodeURIComponent(runId)}/outcomes?after=${after}`, fetchFn),
      checkBatch,
    );
    outcomes.push(...batch.outcomes);
    if (!batch.has_more) {
      break;
    }
    after = batch.next;
  }
  return outcomes;
}

async function actionsToCome(runId: string, fetchFn: typeof fetch): Promise<ActionState[]> {
  const body = await read(`/actuation/v1/runs/${encodeURIComponent(runId)}/actions`, fetchFn);
  if (!Array.isArray(body)) {
    throw new Error("the run's actions are not what the viewer reads");
  }
  return body.map((each) => checked(each, checkState));
}

async function read(url: string, fetchFn: typeof fetch): Promise<unknown> {
  const response = await fetchFn(url);
  if (!response.ok) {
    throw new Error(`the simulator answered ${response.status}`);
  }
  return response.json();
}

function checked<T>(
  body: unknown,
  check: (body: unknown) => { ok: true; value: T } | { ok: false; problems: string[] },
): T {
  const read = check(body);
  if (!read.ok) {
    throw new Error("the run's plan is not what the viewer reads");
  }
  return read.value;
}

function resolvedEntry(outcome: ActionOutcome, startedAt: string): PlanEntry {
  return {
    timeS: secondsInto(startedAt, outcome.started_at ?? outcome.resolved_at),
    planId: outcome.plan_id,
    ref: refText(outcome.ref),
    action: describeAction(outcome.action),
    status: outcome.status,
    reason: outcome.reason ?? null,
    resolved: true,
  };
}

function comingEntry(state: ActionState, startedAt: string): PlanEntry {
  const due = state.due ?? null;
  const at = due === null ? null : typeof due === "string" ? due : due.not_before;
  return {
    timeS: at === null ? null : secondsInto(startedAt, at),
    planId: state.plan_id,
    ref: refText(state.ref),
    action: describeAction(state.action),
    status: state.state,
    reason: null,
    resolved: false,
  };
}

// An instant's milliseconds, as `Date` counts them, in a second.
const MS_PER_S = 1000;

/** An instant, as seconds into a run that started at `startedAt`. */
export function secondsInto(startedAt: string, instant: string): number {
  return (Date.parse(instant) - Date.parse(startedAt)) / MS_PER_S;
}

/** Which action a record is about, as people spell it: `vent`, `tick@3`,
 * `vent/fallback`. */
export function refText(ref: ActionRef): string {
  const occurrence =
    ref.occurrence === undefined || ref.occurrence === null ? "" : `@${ref.occurrence}`;
  return `${ref.action_id}${occurrence}${ref.fallback === true ? "/fallback" : ""}`;
}

// A level as the panels show it, in %.
const PERCENT = 100;

/** What an action does, in words: `fan to 100%`, `heating_day to 22 °C`,
 * `harvest p30's truss t3`. */
export function describeAction(action: Action): string {
  switch (action.kind) {
    case "set_level":
      return action.level === "auto"
        ? `${action.device_id} back to its loop`
        : `${action.device_id} to ${Math.round(action.level * PERCENT)}%`;
    case "set_target":
      return `${action.target} to ${action.value_c} °C`;
    case "water":
      return `water ${action.plant_id}`;
    case "harvest":
      return `harvest ${action.plant_id}'s ${harvested(action)}`;
    case "lower":
      return `lower ${action.plant_id}`;
    case "remove_leaf":
      return `remove ${action.plant_id}'s leaf ${action.leaf_id}`;
    case "inspect":
      return `inspect ${action.plant_id}`;
    default:
      return "an action";
  }
}

function harvested(action: Harvest): string {
  return action.organ_id ? `${action.scope} ${action.organ_id}` : `${action.scope} fruit`;
}
