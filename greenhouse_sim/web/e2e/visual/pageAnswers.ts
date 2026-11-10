import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";

import type { Page, Route } from "@playwright/test";

import { DAY_S } from "../../src/clock";
import type { ScenarioSummary } from "../../src/generated/scenarioSummaryTypes";
import type { Room } from "../../src/landing/generated/roomTypes";
import type { OutcomeBatch } from "../../src/plan/generated/outcomeBatchTypes";
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
  weather: null,
  status: "finished",
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
  weather: null,
  status: "interrupted",
  started_at: "2026-11-02T09:30:00Z",
  simulated_now: "2026-06-03T00:00:00Z",
  time_s: 2 * DAY_S,
  day: 2,
  playing: false,
  following: false,
  parent_kept: false,
  seconds_per_day: 60,
  frontier_s: DAYS_COMPUTED * DAY_S,
  duration_s: DAYS_OF_THE_RUN * DAY_S,
  start_s: 0,
  fork: null,
  targets: [],
  commands: [],
  crop: [],
};

type Answers = readonly (readonly [RegExp, unknown])[];

const ANSWERS: Answers = [
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

// A run of the reference greenhouse, its replay standing at day 2, noon, so that
// its panels show what a run's do: the simulator's answers about it at that
// moment, recorded by `scripts/recordRunAnswers.ts`, its organs left out, as only
// the scene draws them. The viewer checks each against its contract as it reads
// it, so that a stale recording shows as a refusal on the panels' baselines.
const RECORDING = JSON.parse(
  gunzipSync(readFileSync(new URL("./runAnswers.json.gz", import.meta.url))).toString("utf8"),
) as {
  recorded: { scenarioId: string; seed: number; timeS: number };
  answers: Record<string, unknown>;
};
const RECORDED = RECORDING.recorded;
const PANELS_RUN_ID = `${RECORDED.scenarioId}-climate-panels`;
const PANELS_RUN: StoredRun = {
  ...RUN,
  ...PART_WAY,
  run_id: PANELS_RUN_ID,
  scenario_id: RECORDED.scenarioId,
  seed: RECORDED.seed,
  status: "interrupted",
  days_computed: DAYS_COMPUTED,
};
const PANELS_POSITION: PositionState = {
  ...POSITION,
  position_id: "visual-panels-position",
  scenario_id: RECORDED.scenarioId,
  run_id: PANELS_RUN_ID,
  seed: RECORDED.seed,
  simulated_now: "2026-03-02T12:00:00Z",
  time_s: RECORDED.timeS,
  day: Math.floor(RECORDED.timeS / DAY_S),
};
const NO_OUTCOMES: OutcomeBatch = {
  run_id: PANELS_RUN_ID,
  epoch: EPOCH,
  after: 0,
  next: 0,
  simulated_now: PANELS_POSITION.simulated_now,
  has_more: false,
  outcomes: [],
};
const RUN_PANELS_ANSWERS: Answers = [
  [/^\/api\/runs$/, [PANELS_RUN]],
  [/^\/api\/runs\/[^/]+\/epochs\/\d+\/positions$/, PANELS_POSITION],
  [/^\/api\/runs\/[^/]+\/epochs\/\d+\/outcomes$/, NO_OUTCOMES],
  ...ANSWERS,
];
/** The replay the run's panels are drawn on. */
export const PANELS_REPLAY = { runId: PANELS_RUN_ID, epoch: EPOCH };

/** The answer recorded for a question about the run's scenario: by its path, and
 * for the house's air, by whether it asks for the run all off beside it. The
 * replay asks for its first moment before the one its position stands at: that
 * is answered with the recorded moment's answer, said to be of the moment asked,
 * so that the replay moves on to the recorded moment, which is what it draws. */
function recorded(url: URL): unknown {
  const allOff = url.searchParams.get("all_off");
  const answer =
    RECORDING.answers[allOff === null ? url.pathname : `${url.pathname}?all_off=${allOff}`];
  if (answer === null || typeof answer !== "object" || !("time_s" in answer)) {
    return answer;
  }
  return { ...answer, time_s: Number(url.searchParams.get("t") ?? 0) };
}

/**
 * Answers the page's questions to the simulator, which the visual checks do not
 * run, from the above. A question with no answer here is answered 404 and
 * returned, for the test to insist there is none: a page that asks something new
 * must not be drawn as if it had been answered. With `run`, the page is the
 * recorded run's replay, and its scenario's questions are answered too.
 */
export async function answerAsTheSimulator(page: Page, run = false): Promise<string[]> {
  const unanswered: string[] = [];
  const answers = run ? RUN_PANELS_ANSWERS : ANSWERS;
  const answer = async (route: Route) => {
    const url = new URL(route.request().url());
    const found = run ? recorded(url) : undefined;
    if (found !== undefined) {
      await route.fulfill({ json: found });
      return;
    }
    const given = answers.find(([path]) => path.test(url.pathname));
    if (given !== undefined) {
      await route.fulfill({ json: given[1] });
      return;
    }
    if (run || !REFUSED.test(url.pathname)) {
      unanswered.push(`${route.request().method()} ${url.pathname}`);
    }
    await route.fulfill({ status: 404, json: { error: "not in the baselines' answers" } });
  };
  await page.route(/\/(?:api|consumer|actuation)\//, answer);
  return unanswered;
}
