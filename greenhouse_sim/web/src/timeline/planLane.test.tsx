// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

import { LOCAL_OPERATOR } from "../plan/plan";
import { render } from "../testing/render";
import { describeAction, loadPlanLane, type PlanEntry, refText, secondsInto } from "./planLane";
import { describeEntry, TimelineLanes } from "./TimelinePanel";
import type { Timeline } from "./timeline";

const STARTED = "2026-03-01T00:00:00Z";
const RUN = { runId: "climate_box-climate-0f00ba11", epoch: 0, startedAt: STARTED };
const ASAP = { kind: "asap" } as const;
const FAN = { kind: "set_level", device_id: "fan", level: 1 } as const;
const WARM = { kind: "set_target", target: "heating_day", value_c: 22 } as const;

/** An outcome of the viewer's plan, at `at` into the run. */
function outcome(actionId: string, at: string, status: string, reason?: string) {
  return {
    outcome_id: `viewer.${actionId}`,
    greenhouse_id: "climate_box",
    run_id: RUN.runId,
    epoch: 0,
    plan_id: "viewer",
    revision: 1,
    ref: { action_id: actionId },
    action: FAN,
    timing: ASAP,
    principal: LOCAL_OPERATOR,
    status,
    due: at,
    ...(status === "executed" ? { started_at: at, finished_at: at } : {}),
    resolved_at: at,
    ...(reason === undefined ? {} : { reason }),
  };
}

function batch(outcomes: unknown[], after: number, hasMore: boolean) {
  return {
    run_id: RUN.runId,
    epoch: 0,
    after,
    next: after + outcomes.length,
    simulated_now: "2026-03-01T07:00:00Z",
    has_more: hasMore,
    outcomes,
  };
}

const COMING = {
  plan_id: "viewer",
  revision: 2,
  ref: { action_id: "change_3" },
  action: WARM,
  timing: { kind: "at", at: "2026-03-01T08:00:00Z" },
  due: "2026-03-01T08:00:00Z",
  principal: LOCAL_OPERATOR,
  state: "assigned",
};

function answering(byUrl: Record<string, unknown>): typeof fetch {
  return vi.fn(async (url: string) =>
    url in byUrl ? new Response(JSON.stringify(byUrl[url])) : new Response("{}", { status: 404 }),
  ) as unknown as typeof fetch;
}

const OUTCOMES = `/consumer/v1/runs/${RUN.runId}/outcomes`;
const ACTIONS = `/actuation/v1/runs/${RUN.runId}/actions`;

describe("a followed run's plan lane", () => {
  it("reads the whole outcome log, page by page, and what is still to come", async () => {
    const fetchFn = answering({
      [`${OUTCOMES}?after=0`]: batch(
        [outcome("change_1", "2026-03-01T06:00:00Z", "executed")],
        0,
        true,
      ),
      [`${OUTCOMES}?after=1`]: batch(
        [outcome("change_2", "2026-03-01T06:30:00Z", "refused", "no device 'fan_9'")],
        1,
        false,
      ),
      [ACTIONS]: [COMING],
    });

    const lane = await loadPlanLane(RUN, fetchFn);

    expect(lane).toEqual({
      status: "loaded",
      entries: [
        {
          timeS: 6 * 3600,
          planId: "viewer",
          ref: "change_1",
          action: "fan to 100%",
          status: "executed",
          reason: null,
          resolved: true,
        },
        {
          timeS: 6.5 * 3600,
          planId: "viewer",
          ref: "change_2",
          action: "fan to 100%",
          status: "refused",
          reason: "no device 'fan_9'",
          resolved: true,
        },
        {
          timeS: 8 * 3600,
          planId: "viewer",
          ref: "change_3",
          action: "heating_day to 22 °C",
          status: "assigned",
          reason: null,
          resolved: false,
        },
      ],
    });
  });

  it("is unavailable, saying why, when a log is not what the viewer reads", async () => {
    const fetchFn = answering({ [`${OUTCOMES}?after=0`]: { outcomes: "none" }, [ACTIONS]: [] });

    expect(await loadPlanLane(RUN, fetchFn)).toEqual({
      status: "unavailable",
      reason: "the run's plan is not what the viewer reads",
    });
  });

  it("says each action in words, and which it is", () => {
    expect(describeAction({ kind: "set_level", device_id: "roof_vent", level: 0.25 })).toBe(
      "roof_vent to 25%",
    );
    expect(describeAction({ kind: "set_level", device_id: "heater", level: "auto" })).toBe(
      "heater back to its loop",
    );
    expect(describeAction(WARM)).toBe("heating_day to 22 °C");
    expect(
      describeAction({ kind: "harvest", plant_id: "p30", scope: "truss", organ_id: "t3" }),
    ).toBe("harvest p30's truss t3");
    expect(describeAction({ kind: "lower", plant_id: "p30", by_cm: 20 })).toBe("lower p30");
    expect(refText({ action_id: "tick", occurrence: 3 })).toBe("tick@3");
    expect(refText({ action_id: "vent", fallback: true })).toBe("vent/fallback");
    expect(secondsInto(STARTED, "2026-03-02T01:00:00Z")).toBe(25 * 3600);
  });
});

const WINDOW: Timeline = {
  fromS: 6 * 3600,
  untilS: 7 * 3600,
  processes: ["commands"],
  subjects: [],
  kinds: [],
  timesS: [],
  process: [],
  subject: [],
  kind: [],
};

function entry(timeS: number | null, status: PlanEntry["status"], resolved: boolean): PlanEntry {
  return {
    timeS,
    planId: "viewer",
    ref: `at_${timeS}`,
    action: "fan to 100%",
    status,
    reason: status === "refused" ? "not authorised" : null,
    resolved,
  };
}

describe("a followed run's plan lane, drawn", () => {
  it("draws and lists the window's actions in the order of their moments, with what became of each", () => {
    const shown = render(
      <TimelineLanes
        timeline={WINDOW}
        time={6.5 * 3600}
        plan={[
          entry(6.75 * 3600, "refused", true),
          entry(6 * 3600, "executed", true),
          entry(9 * 3600, "assigned", false),
          entry(null, "waiting", false),
        ]}
      />,
    );

    expect(shown.container.querySelector('[data-testid="timeline-plan"]')?.textContent).toBe(
      "plan, 3",
    );
    expect(
      [...shown.container.querySelectorAll('[data-testid="timeline-plan-entry"]')].map(
        (item) => item.textContent,
      ),
    ).toEqual([
      "6 h 00 min, fan to 100% (viewer/at_21600): executed",
      "6 h 45 min, fan to 100% (viewer/at_24300): refused: not authorised",
      "as soon as it can, fan to 100% (viewer/at_null): waiting",
    ]);
    expect(shown.container.querySelector(".timeline-plan-ran")?.getAttribute("d")).toBe("M0 0V10");
    expect(shown.container.querySelector(".timeline-plan-not-ran")?.getAttribute("d")).toBe(
      "M180 0V10",
    );
  });

  it("is not drawn for a run not followed", () => {
    const shown = render(<TimelineLanes timeline={WINDOW} time={6.5 * 3600} />);

    expect(shown.container.querySelector('[data-testid="timeline-plan"]')).toBeNull();
    expect(describeEntry(entry(null, "waiting", false))).toBe(
      "as soon as it can, fan to 100% (viewer/at_null): waiting",
    );
  });
});
