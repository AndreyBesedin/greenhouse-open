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

function answering(byUrl: Record<string, unknown>): typeof fetch {
  return vi.fn(async (url: string) =>
    url in byUrl ? new Response(JSON.stringify(byUrl[url])) : new Response("{}", { status: 404 }),
  ) as unknown as typeof fetch;
}

const OUTCOMES = `/api/runs/${RUN.runId}/epochs/0/outcomes`;

describe("a replayed epoch's plan lane", () => {
  it("reads the outcomes its epoch delivered by the moment shown, page by page, through the store alone", async () => {
    const fetchFn = answering({
      [`${OUTCOMES}?after=0&t=25200`]: batch(
        [outcome("change_1", "2026-03-01T06:00:00Z", "executed")],
        0,
        true,
      ),
      [`${OUTCOMES}?after=1&t=25200`]: batch(
        [outcome("change_2", "2026-03-01T06:30:00Z", "refused", "no device 'fan_9'")],
        1,
        false,
      ),
    });

    const lane = await loadPlanLane(RUN, fetchFn, 7 * 3600);

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
        },
        {
          timeS: 6.5 * 3600,
          planId: "viewer",
          ref: "change_2",
          action: "fan to 100%",
          status: "refused",
          reason: "no device 'fan_9'",
        },
      ],
    });
    // Neither the consumer interface nor the gateway is asked (P22.3): the
    // store keeps no list of the actions still to come.
    expect(vi.mocked(fetchFn).mock.calls.map(([url]) => url)).toEqual([
      `${OUTCOMES}?after=0&t=25200`,
      `${OUTCOMES}?after=1&t=25200`,
    ]);
  });

  it("is unavailable, saying why, when a log is not what the viewer reads", async () => {
    const fetchFn = answering({ [`${OUTCOMES}?after=0&t=0`]: { outcomes: "none" } });

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

function entry(timeS: number, status: PlanEntry["status"]): PlanEntry {
  return {
    timeS,
    planId: "viewer",
    ref: `at_${timeS}`,
    action: "fan to 100%",
    status,
    reason: status === "refused" ? "not authorised" : null,
  };
}

describe("a replayed epoch's plan lane, drawn", () => {
  it("draws and lists the window's actions in the order of their moments, with what became of each", () => {
    const shown = render(
      <TimelineLanes
        timeline={WINDOW}
        time={6.5 * 3600}
        plan={[
          entry(6.75 * 3600, "refused"),
          entry(6 * 3600, "executed"),
          entry(9 * 3600, "executed"),
        ]}
      />,
    );

    expect(shown.container.querySelector('[data-testid="timeline-plan"]')?.textContent).toBe(
      "plan, 2",
    );
    expect(
      [...shown.container.querySelectorAll('[data-testid="timeline-plan-entry"]')].map(
        (item) => item.textContent,
      ),
    ).toEqual([
      "6 h 00 min, fan to 100% (viewer/at_21600): executed",
      "6 h 45 min, fan to 100% (viewer/at_24300): refused: not authorised",
    ]);
    expect(shown.container.querySelector(".timeline-plan-ran")?.getAttribute("d")).toBe("M0 0V10");
    expect(shown.container.querySelector(".timeline-plan-not-ran")?.getAttribute("d")).toBe(
      "M180 0V10",
    );
    // Nothing is still to come in a lane the store reads.
    expect(
      [...shown.container.querySelectorAll('svg[aria-label^="plan:"] path')].map((path) =>
        path.getAttribute("class"),
      ),
    ).toEqual(["timeline-plan-ran", "timeline-plan-not-ran"]);
  });

  it("is not drawn for a run not replayed", () => {
    const shown = render(<TimelineLanes timeline={WINDOW} time={6.5 * 3600} />);

    expect(shown.container.querySelector('[data-testid="timeline-plan"]')).toBeNull();
    expect(describeEntry(entry(6 * 3600, "missed"))).toBe(
      "6 h 00 min, fan to 100% (viewer/at_21600): missed",
    );
  });
});
