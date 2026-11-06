import type { Page, Route } from "@playwright/test";

import { DAY_S } from "../../src/clock";
import type { ScenarioSummary } from "../../src/generated/scenarioSummaryTypes";
import type { Room } from "../../src/landing/generated/roomTypes";
import type { PositionState } from "../../src/scene/generated/positionTypes";
import type { StoredRun } from "../../src/scene/generated/storedRunTypes";

/** The scenario, run and epoch the pages' baselines show. */
export const SCENARIO_ID = "visual_house";
export const RUN_ID = "visual_house-climate-abc";
export const EPOCH = 0;
/** The moment the pages are drawn at, for whatever says how long ago something was. */
export const DRAWN_AT = "2026-11-03T12:00:00Z";

const DAYS_OF_THE_RUN = 10;
const DAYS_COMPUTED = 6;
const BYTES_KEPT = 8 * 1024 * 1024;

// What the simulator answers, as its contracts type them, so that a change of a
// contract fails the type check that comes before the baselines' build, rather
// than quietly drawing a page's refusal.
const SCENARIOS: ScenarioSummary[] = [
  {
    id: SCENARIO_ID,
    name: "A house for the baselines",
    description: "What the pages' baselines list; it is never run.",
    plants: 32,
    duration_days: DAYS_OF_THE_RUN,
    crop_model: "simple",
    daily: [],
    openings: [],
    opening_day: null,
    layouts: ["default"],
    weathers: ["default"],
    thermostat: null,
  },
];

export const RUN: StoredRun = {
  run_id: RUN_ID,
  epoch: EPOCH,
  scenario_id: SCENARIO_ID,
  seed: 7,
  layout: "default",
  status: "finished",
  paused: false,
  frontier_s: DAYS_OF_THE_RUN * DAY_S,
  duration_s: DAYS_OF_THE_RUN * DAY_S,
  progress: 1,
  created_at: "2026-11-02T09:30:00Z",
  size_bytes: BYTES_KEPT,
  start_s: 0,
  fork: null,
  stopping: false,
  damaged: false,
  days_computed: DAYS_OF_THE_RUN,
  cpu_s: null,
  peak_memory_bytes: null,
  wall_s: null,
  past_limit: false,
  reason: null,
};

// Every state a run's status is told in, since each has its own colours; one
// measured by its workers and ended by a limit, which says why under its row.
const PART_WAY = { frontier_s: DAYS_COMPUTED * DAY_S, progress: DAYS_COMPUTED / DAYS_OF_THE_RUN };
const MEASURED = {
  days_computed: DAYS_COMPUTED,
  cpu_s: 812,
  peak_memory_bytes: 331_000_000,
  wall_s: 905,
};
const RUNS: StoredRun[] = [
  RUN,
  {
    ...RUN,
    ...PART_WAY,
    ...MEASURED,
    epoch: EPOCH + 1,
    status: "failed",
    past_limit: true,
    reason:
      "it took 812 s of a core, past the limit of 800 s on one run: what it committed can be read, and it can be carried on once that limit is raised",
  },
  { ...RUN, ...PART_WAY, days_computed: DAYS_COMPUTED, epoch: EPOCH + 2, status: "interrupted" },
];

/** The room for runs the start page's baseline shows: one worker of two busy. */
export const ROOM: Room = {
  workers_busy: 1,
  workers_limit: 2,
  runs_waiting: 0,
  runs_waiting_limit: 200,
  disk_free_bytes: 45_200_000_000,
  disk_free_limit_bytes: 2_000_000_000,
  refusal: null,
};

// Stopped part of the way, so that a replay's track shows both what is computed
// and what is not, and asks the simulator nothing more.
const POSITION: PositionState = {
  position_id: "visual-position",
  scenario_id: SCENARIO_ID,
  run_id: RUN_ID,
  epoch: EPOCH,
  layout: "default",
  seed: 7,
  status: "interrupted",
  started_at: "2026-11-02T09:30:00Z",
  simulated_now: "2026-06-03T00:00:00Z",
  time_s: 2 * DAY_S,
  day: 2,
  playing: false,
  following: false,
  parent_kept: false,
  paused: false,
  seconds_per_day: 60,
  frontier_s: DAYS_COMPUTED * DAY_S,
  duration_s: DAYS_OF_THE_RUN * DAY_S,
  start_s: 0,
  fork: null,
  targets: [],
  commands: [],
  crop: [],
};

const ANSWERS: readonly (readonly [RegExp, unknown])[] = [
  [/^\/api\/scenarios$/, SCENARIOS],
  [/^\/api\/runs$/, RUNS],
  [/^\/api\/room$/, ROOM],
  [/^\/api\/drafts$/, []],
  [/^\/api\/runs\/[^/]+\/epochs\/\d+\/positions$/, POSITION],
  [/^\/api\/positions\/[^/]+\/close$/, {}],
];
// What a replay's viewer asks of its scenario. Refused, as a scene is not what
// the replay's baseline holds (`pages.css`).
const REFUSED = /^\/api\/scenarios\/[^/]+\/./;

/**
 * Answers the page's questions to the simulator, which the visual checks do not
 * run, from the above. A question with no answer here is answered 404 and
 * returned, for the test to insist there is none: a page that asks something new
 * must not be drawn as if it had been answered.
 */
export async function answerAsTheSimulator(page: Page): Promise<string[]> {
  const unanswered: string[] = [];
  const answer = async (route: Route) => {
    const { pathname } = new URL(route.request().url());
    const found = ANSWERS.find(([path]) => path.test(pathname));
    if (found !== undefined) {
      await route.fulfill({ json: found[1] });
      return;
    }
    if (!REFUSED.test(pathname)) {
      unanswered.push(`${route.request().method()} ${pathname}`);
    }
    await route.fulfill({ status: 404, json: { error: "not in the baselines' answers" } });
  };
  await page.route(/\/(?:api|consumer|actuation)\//, answer);
  return unanswered;
}
