import { contractCheck } from "../loadJson";
import { OUTCOME_BATCH_SCHEMA } from "../plan/generated/outcomeBatchSchema";
import type {
  ActionOutcome,
  ActionRef,
  OutcomeBatch,
  OutcomeStatus,
} from "../plan/generated/outcomeBatchTypes";
import type { Action, Harvest } from "../plan/generated/planTypes";

/**
 * The plan lane of a stored epoch replayed (P13.8, P22.3, decision 0074): what
 * its plans had due and what became of each and why, as the outcomes its epoch
 * delivered by the moment shown say it, read through the run store
 * (`/api/runs/{run}/epochs/{n}/outcomes?t=`). The store keeps no list of the
 * actions still to come, so the lane has none. Each is placed at its moment, in
 * seconds into the run, as the timeline places its events: where its action
 * started, or was resolved without starting.
 */
export interface PlanEntry {
  /** Its moment, in seconds into the run. */
  timeS: number;
  planId: string;
  /** Which action, as people spell it: `change_1`, `tick@3`. */
  ref: string;
  /** What it does, in words. */
  action: string;
  /** What became of it. */
  status: OutcomeStatus;
  reason: string | null;
}

export type PlanLaneState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; entries: PlanEntry[] };

/** The epoch whose plan lane is drawn: its run's identifier, its number, and
 * the instant its clock started at; and how many times the viewer has given it
 * a change (`version`), so that the lane is read again after each, even at a
 * moment that does not move, as a paused replay's does not. */
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

/** An epoch's plan lane: the outcomes it delivered by `atS`, seconds into the
 * run. Every failure becomes a state. */
export async function loadPlanLane(
  run: PlanLaneRun,
  fetchFn: typeof fetch = fetch,
  atS = 0,
): Promise<PlanLaneState> {
  try {
    const outcomes = await allOutcomes(outcomesUrl(run, atS), fetchFn);
    return {
      status: "loaded",
      entries: outcomes.map((outcome) => entryOf(outcome, run.startedAt)),
    };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

/** Where an epoch's outcomes after a cursor are read, as delivered by `atS`. */
function outcomesUrl(run: PlanLaneRun, atS: number): (after: number) => string {
  const runId = encodeURIComponent(run.runId);
  return (after) => `/api/runs/${runId}/epochs/${run.epoch}/outcomes?after=${after}&t=${atS}`;
}

async function allOutcomes(
  url: (after: number) => string,
  fetchFn: typeof fetch,
): Promise<ActionOutcome[]> {
  const outcomes: ActionOutcome[] = [];
  let after = 0;
  for (let page = 0; page < MOST_PAGES; page += 1) {
    const batch = checked(await read(url(after), fetchFn), checkBatch);
    outcomes.push(...batch.outcomes);
    if (!batch.has_more) {
      break;
    }
    after = batch.next;
  }
  return outcomes;
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

function entryOf(outcome: ActionOutcome, startedAt: string): PlanEntry {
  return {
    timeS: secondsInto(startedAt, outcome.started_at ?? outcome.resolved_at),
    planId: outcome.plan_id,
    ref: refText(outcome.ref),
    action: describeAction(outcome.action),
    status: outcome.status,
    reason: outcome.reason ?? null,
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
