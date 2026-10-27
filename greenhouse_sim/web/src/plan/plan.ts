/**
 * The plan the viewer gives a run it follows (P13.8, decision 0046): what a
 * person sets in its panels, a device's level or a heating target, as the
 * local operator's actions, given through the run's gateway
 * (`/actuation/v1`), the protocol's write side, as any client would. Each
 * is to be carried out as soon as the run can: a level at once, a target on
 * the minute.
 *
 * One plan, `viewer`, revised at each change: a revision keeps the actions
 * of the one before not yet resolved and adds the new ones, each under an
 * identifier of its own. What a revision leaves out that was resolved keeps
 * its outcome, so the plan holds no more than is still to come.
 */

import { contractCheck } from "../loadJson";
import { loadPlayback } from "../scene/playback";
import { PLAN_STATE_SCHEMA } from "./generated/planStateSchema";
import type { PlanState } from "./generated/planStateTypes";
import type { Action, Plan, PlannedAction, Principal } from "./generated/planTypes";
import { RECEIPT_SCHEMA } from "./generated/receiptSchema";
import type { Receipt } from "./generated/receiptTypes";

/** The viewer's plan of a run it follows. */
export const VIEWER_PLAN = "viewer";
/** Whom the simulator's local API takes every write from (decision 0052). */
export const LOCAL_OPERATOR: Principal = { kind: "person", id: "local_operator" };

const ACTUATION = "/actuation/v1";
const NOT_FOUND = 404;
// How many times a revision is given, read again each time: once more if
// another revision, from another view, came first.
const ATTEMPTS = 2;
// The identifiers the viewer gives its actions: `change_1`, `change_2`...
const CHANGE = "change_";

/** What became of actions given: taken into the run's plan, or refused,
 * and why, in the gateway's words. */
export type Given = { status: "given" } | { status: "refused"; reason: string };

/** The run a playback plays, as the gateway names it. */
export interface PlayedRun {
  runId: string;
  epoch: number;
}

const checkReceipt = contractCheck<Receipt>(RECEIPT_SCHEMA, "the receipt");
const checkPlanState = contractCheck<PlanState>(PLAN_STATE_SCHEMA, "the plan");

/** Where a run's plan is given, and read. */
export function plansUrl(runId: string): string {
  return `${ACTUATION}/runs/${encodeURIComponent(runId)}/plans`;
}

/** A level for a device, its equipment's or a door's or vent's. */
export function setLevel(deviceId: string, level: number): Action {
  return { kind: "set_level", device_id: deviceId, level };
}

/** A heating target, `heating_day` or `heating_night`, in °C. */
export function setTarget(target: string, valueC: number): Action {
  return { kind: "set_target", target: target as "heating_day", value_c: valueC };
}

/**
 * The plan's next revision with `actions` added, each as soon as the run can
 * carry it out: the revision in force's actions still to come kept as they
 * are, under their identifiers, and each new one under one no revision has
 * used. Its first revision if `state` is null.
 */
export function nextRevision(state: PlanState | null, run: PlayedRun, actions: Action[]): Plan {
  const pending = new Set(state?.unresolved.map((each) => each.ref.action_id) ?? []);
  const kept = (state?.plan.actions ?? []).filter((each) => pending.has(each.action_id));
  const used = [
    ...(state?.plan.actions.map((each) => each.action_id) ?? []),
    ...(state?.outcomes.map((each) => each.ref.action_id) ?? []),
  ];
  const last = Math.max(0, ...used.map(changeNumber));
  const added: PlannedAction[] = actions.map((action, index) => ({
    action_id: `${CHANGE}${last + index + 1}`,
    action,
    timing: { kind: "asap" },
    proposed_by: LOCAL_OPERATOR,
  }));
  return {
    plan_id: VIEWER_PLAN,
    run_id: run.runId,
    epoch: run.epoch,
    revision: (state?.plan.revision ?? 0) + 1,
    actions: [...kept, ...added],
  };
}

function changeNumber(actionId: string): number {
  const number = actionId.startsWith(CHANGE) ? Number(actionId.slice(CHANGE.length)) : 0;
  return Number.isInteger(number) ? number : 0;
}

/**
 * Gives the run a scenario's playback plays `actions`, as the next revision
 * of the viewer's plan: the run and its epoch read from the playback, then
 * the plan as it stands, then the revision given. A receipt that refuses it
 * whole, as stale since another revision came first, is answered by giving
 * it again once, read anew; an action refused at once is refused, with its
 * outcome's reason.
 */
export async function giveToPlan(
  scenarioId: string,
  actions: Action[],
  fetchFn: typeof fetch = fetch,
): Promise<Given> {
  let refusal = "the run's gateway could not be reached";
  for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
    try {
      const played = await loadPlayback(scenarioId, fetchFn);
      if (played.status !== "loaded") {
        return { status: "refused", reason: "the run is not played back" };
      }
      const run = { runId: played.state.runId, epoch: played.state.epoch };
      const state = await planState(run.runId, fetchFn);
      const receipt = await given(nextRevision(state, run, actions), fetchFn);
      if (!receipt.accepted) {
        refusal = (receipt.errors ?? []).join("; ") || "the plan was refused";
        continue;
      }
      if ((receipt.refused ?? []).length > 0) {
        return { status: "refused", reason: await reasons(run.runId, receipt, fetchFn) };
      }
      return { status: "given" };
    } catch (error) {
      refusal = error instanceof Error ? error.message : String(error);
    }
  }
  return { status: "refused", reason: refusal };
}

/** The viewer's plan of a run as its gateway holds it, or null if it has
 * none yet. */
async function planState(runId: string, fetchFn: typeof fetch): Promise<PlanState | null> {
  const response = await fetchFn(`${plansUrl(runId)}/${VIEWER_PLAN}`);
  if (response.status === NOT_FOUND) {
    return null;
  }
  return checked(response, checkPlanState);
}

async function given(plan: Plan, fetchFn: typeof fetch): Promise<Receipt> {
  const response = await fetchFn(plansUrl(plan.run_id), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(plan),
  });
  return checked(response, checkReceipt);
}

/** Why the actions a receipt refused were refused, as their outcomes say. */
async function reasons(runId: string, receipt: Receipt, fetchFn: typeof fetch): Promise<string> {
  const state = await planState(runId, fetchFn);
  const refused = new Set((receipt.refused ?? []).map((ref) => ref.action_id));
  const said = (state?.outcomes ?? [])
    .filter((outcome) => refused.has(outcome.ref.action_id))
    .map((outcome) => outcome.reason ?? "refused");
  return said.length > 0 ? [...new Set(said)].join("; ") : "refused";
}

async function checked<T>(
  response: Response,
  check: (body: unknown) => { ok: true; value: T } | { ok: false; problems: string[] },
): Promise<T> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON: said below.
  }
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body ? String(body.detail) : "";
    throw new Error(detail || `the run's gateway answered ${response.status}`);
  }
  const read = check(body);
  if (!read.ok) {
    throw new Error("the gateway's answer is not what the viewer reads");
  }
  return read.value;
}
