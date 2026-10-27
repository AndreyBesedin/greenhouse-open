import { describe, expect, it, vi } from "vitest";

import type { PlanState } from "./generated/planStateTypes";
import {
  cropAction,
  giveToPlan,
  LOCAL_OPERATOR,
  nextRevision,
  plansUrl,
  setLevel,
  setTarget,
  VIEWER_PLAN,
} from "./plan";

const RUN = { runId: "reference_greenhouse-climate-2f2dc84a", epoch: 1 };
const PLAYBACK = {
  scenario_id: "reference_greenhouse",
  run_id: RUN.runId,
  layout: "default",
  epoch: RUN.epoch,
  greenhouse_id: "reference_greenhouse",
  started_at: "2026-02-28T23:00:00Z",
  simulated_now: "2026-03-02T11:00:30Z",
  time_s: 129_630,
  day: 1,
  playing: true,
  seconds_per_day: 10,
  worked_out_s: 172_800,
  every_s: 300,
  targets: [],
  commands: [],
  crop: [],
};
const ASAP = { kind: "asap" } as const;
const OPEN = setLevel("roof_vent", 0.5);
const WARM = setTarget("heating_day", 22);

function planned(actionId: string, action = OPEN) {
  return { action_id: actionId, action, timing: ASAP, proposed_by: LOCAL_OPERATOR };
}

/** The viewer's plan as a gateway holds it, at its second revision:
 * `change_2` still to come, and `change_1` done. */
const HELD: PlanState = {
  plan: {
    plan_id: VIEWER_PLAN,
    run_id: RUN.runId,
    epoch: RUN.epoch,
    revision: 2,
    actions: [planned("change_1"), planned("change_2", WARM)],
  },
  owner: LOCAL_OPERATOR,
  sequence: 2,
  unresolved: [
    {
      plan_id: VIEWER_PLAN,
      revision: 2,
      ref: { action_id: "change_2" },
      action: WARM,
      timing: ASAP,
      principal: LOCAL_OPERATOR,
      state: "assigned",
    },
  ],
  outcomes: [outcome("change_1", "executed")],
  authorisation: [],
};

function outcome(actionId: string, status: string, reason?: string) {
  return {
    outcome_id: `${VIEWER_PLAN}.${actionId}`,
    greenhouse_id: "reference_greenhouse",
    run_id: RUN.runId,
    epoch: RUN.epoch,
    plan_id: VIEWER_PLAN,
    revision: 1,
    ref: { action_id: actionId },
    action: OPEN,
    timing: ASAP,
    principal: LOCAL_OPERATOR,
    status: status as "executed",
    due: "2026-03-02T11:00:30Z",
    resolved_at: "2026-03-02T11:00:30Z",
    ...(reason === undefined ? {} : { reason }),
  };
}

/** A fetch that answers each request in turn with `answers`, and records
 * what it was asked. */
function answering(...answers: [number, unknown][]) {
  const asked: { url: string; init: RequestInit | undefined }[] = [];
  const fetchFn = vi.fn(async (url: string, init?: RequestInit) => {
    asked.push({ url, init });
    const [status, body] = answers[asked.length - 1] ?? [500, {}];
    return new Response(JSON.stringify(body), { status });
  });
  return { fetchFn: fetchFn as unknown as typeof fetch, asked };
}

function bodyOf(init: RequestInit | undefined): unknown {
  return JSON.parse(String(init?.body));
}

describe("the viewer's plan of a run it follows", () => {
  it("is given first as its first revision, each action as soon as the run can", () => {
    expect(nextRevision(null, RUN, [OPEN, WARM])).toEqual({
      plan_id: VIEWER_PLAN,
      run_id: RUN.runId,
      epoch: RUN.epoch,
      revision: 1,
      actions: [planned("change_1"), planned("change_2", WARM)],
    });
  });

  it("keeps what is still to come, and gives new actions identifiers no revision used", () => {
    const next = nextRevision(HELD, RUN, [OPEN]);

    expect(next.revision).toBe(3);
    // change_1 is done, and left out: its outcome stands.
    expect(next.actions).toEqual([planned("change_2", WARM), planned("change_3")]);
  });

  it("is given through the run's gateway, read first as the playback and the plan stand", async () => {
    const { fetchFn, asked } = answering(
      [200, PLAYBACK],
      [404, { detail: "no plan" }],
      [200, { accepted: true, plan_id: VIEWER_PLAN, revision: 1 }],
    );

    expect(await giveToPlan("reference_greenhouse", [OPEN], fetchFn)).toEqual({ status: "given" });
    expect(asked.map(({ url, init }) => [init?.method ?? "GET", url])).toEqual([
      ["GET", "/api/scenarios/reference_greenhouse/playback"],
      ["GET", `${plansUrl(RUN.runId)}/${VIEWER_PLAN}`],
      ["POST", plansUrl(RUN.runId)],
    ]);
    expect(bodyOf(asked[2]?.init)).toEqual(nextRevision(null, RUN, [OPEN]));
  });

  it("is given again, read anew, when another revision came first", async () => {
    const { fetchFn, asked } = answering(
      [200, PLAYBACK],
      [404, {}],
      [200, { accepted: false, errors: ["stale: revision 1 is not newer than 1"] }],
      [200, PLAYBACK],
      [200, HELD],
      [200, { accepted: true }],
    );

    expect(await giveToPlan("reference_greenhouse", [OPEN], fetchFn)).toEqual({ status: "given" });
    expect(bodyOf(asked[5]?.init)).toEqual(nextRevision(HELD, RUN, [OPEN]));
  });

  it("says why, in the gateway's words, what the run refuses", async () => {
    const refusedAtOnce = answering(
      [200, PLAYBACK],
      [200, HELD],
      [200, { accepted: true, refused: [{ action_id: "change_3" }] }],
      [200, { ...HELD, outcomes: [outcome("change_3", "refused", "no device 'fan_9'")] }],
    );
    expect(
      await giveToPlan("reference_greenhouse", [setLevel("fan_9", 1)], refusedAtOnce.fetchFn),
    ).toEqual({ status: "refused", reason: "no device 'fan_9'" });

    const refusedWhole = answering(
      [200, PLAYBACK],
      [404, {}],
      [200, { accepted: false, errors: ["local_operator may not set_level"] }],
      [200, PLAYBACK],
      [404, {}],
      [200, { accepted: false, errors: ["local_operator may not set_level"] }],
    );
    expect(await giveToPlan("reference_greenhouse", [OPEN], refusedWhole.fetchFn)).toEqual({
      status: "refused",
      reason: "local_operator may not set_level",
    });
  });

  it("is refused for a run not played back, or a gateway that answers otherwise", async () => {
    const unstarted = answering([404, { error: "no playback" }]);
    expect(await giveToPlan("reference_greenhouse", [OPEN], unstarted.fetchFn)).toEqual({
      status: "refused",
      reason: "the run is not played back",
    });

    const finished = answering(
      [200, PLAYBACK],
      [404, {}],
      [409, { detail: "the run has finished" }],
      [200, PLAYBACK],
      [404, {}],
      [409, { detail: "the run has finished" }],
    );
    expect(await giveToPlan("reference_greenhouse", [OPEN], finished.fetchFn)).toEqual({
      status: "refused",
      reason: "the run has finished",
    });
  });

  it("takes a plant's work as the protocol's action, as the plant lab names it", () => {
    const on = (
      kind: "remove_leaf" | "harvest_fruit" | "harvest_truss" | "lower_stem",
      target: string,
    ) => cropAction({ day: 3, plantId: "p30", kind, target });

    expect(on("remove_leaf", "p30_n02_leaf")).toEqual({
      kind: "remove_leaf",
      plant_id: "p30",
      leaf_id: "p30_n02_leaf",
    });
    expect(on("harvest_fruit", "p30_t03_f01")).toEqual({
      kind: "harvest",
      plant_id: "p30",
      scope: "fruit",
      organ_id: "p30_t03_f01",
    });
    expect(on("harvest_truss", "p30_t03")).toMatchObject({ scope: "truss", organ_id: "p30_t03" });
    expect(on("lower_stem", "1")).toEqual({ kind: "lower", plant_id: "p30", by_internodes: 1 });
  });
});
