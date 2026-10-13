import { defineConfig, devices } from "@playwright/test";

import { REUSE_TEST_SERVERS, simulatorApi, TEST_SIMULATOR_API_PORT } from "./simulatorApi.ts";

// The smoke test runs the real thing: the simulator's local API and the
// production build of the viewer, in Chromium. PYTHON names an interpreter
// that has greenhouse-sim installed.
const PYTHON = process.env.PYTHON ?? "python";
const PREVIEW_PORT = 4317;
const IN_CI = process.env.CI !== undefined;
// Screenshot comparisons and the benchmark have their own configurations.
const ELSEWHERE = ["visual/**", "bench/**"];
// P00's final QA drives a shared live run, so it runs once the others pass.
const RENDERER_SMOKE = "renderer-smoke.spec.ts";
// The plant lab grows a row of thousands of entities on its later days, and
// times out when the climate's runs share the simulator with it: it runs on
// its own, once the others and P00's pass.
const PLANT_LAB = "plant-lab.spec.ts";
// P07's final QA works the climate through a whole day, so it runs on its
// own, last, and slows none of the others.
const WEATHER_DAY = "weather-day.spec.ts";
// P08's checks of the sun's light work climate runs out to noon, so they too
// run on their own, after the plant lab, and P07's after them.
const SUN = ["light.spec.ts", "solar-lab.spec.ts", "solar-day.spec.ts"];
// P09's checks through a run's days work a climate run on each day they
// visit, and the reference greenhouse's its house and crop through days
// too: two at once starve each other's waits on a slow machine, so each
// runs alone, one after another, after P07's.
const ONE_BY_ONE = [
  "season.spec.ts",
  "daily-schedule.spec.ts",
  "checkpoints.spec.ts",
  "crop.spec.ts",
  "reference-schedule.spec.ts",
  // P09.9's demo walks through the whole final QA, last of all.
  "demo.spec.ts",
];

interface Stage {
  name: string;
  testMatch?: string[];
  testIgnore?: string[];
}
// The specs above, each a stage of its own, in the order they run.
const ALONE: Stage[] = [
  { name: "renderer-smoke", testMatch: [RENDERER_SMOKE] },
  { name: "plant-lab", testMatch: [PLANT_LAB] },
  { name: "sun", testMatch: SUN },
  { name: "weather-day", testMatch: [WEATHER_DAY] },
  ...ONE_BY_ONE.map((spec) => ({ name: spec.replace(".spec.ts", ""), testMatch: [spec] })),
];
// Every browser test, stage by stage: each stage runs once the one before
// it has passed, so that none of those above shares the simulator with
// another. The first is every other spec, run in parallel.
const STAGES: Stage[] = [
  {
    name: "chromium",
    testIgnore: [...ELSEWHERE, ...ALONE.flatMap((stage) => stage.testMatch ?? [])],
  },
  ...ALONE,
];
// On CI the stages are cut into lanes that run at once, each on a machine
// of its own with a simulator of its own, so that a stage still shares it
// with none of those above (decision 0032). A lane starts at the first
// stage and at each of these, and is named for the stage it starts at.
// Here, on one machine, the lanes run one after another, as one.
const LANE_STARTS = ["renderer-smoke", "weather-day", "crop"];
// The lane a CI job runs, and how many lanes CI runs: all of them
// (`.github/workflows/ci.yml`).
const LANE = process.env.BROWSER_TEST_LANE;
const LANES_RUN = process.env.BROWSER_TEST_LANES;

/** The stages to run: the lane `BROWSER_TEST_LANE` names, or all of them. */
function stagesToRun(): Stage[] {
  if (LANE === undefined) {
    return STAGES;
  }
  const names = STAGES.filter(
    (stage, index) => index === 0 || LANE_STARTS.includes(stage.name),
  ).map((stage) => stage.name);
  if (LANES_RUN !== undefined && Number(LANES_RUN) !== names.length) {
    throw new Error(`CI runs ${LANES_RUN} lanes of browser tests, not all of ${names.join(", ")}`);
  }
  if (!names.includes(LANE)) {
    throw new Error(
      `No lane of browser tests starts at ${LANE}; they start at ${names.join(", ")}`,
    );
  }
  const start = STAGES.findIndex((stage) => stage.name === LANE);
  const next = STAGES.findIndex((stage, index) => index > start && names.includes(stage.name));
  return STAGES.slice(start, next === -1 ? STAGES.length : next);
}

export default defineConfig({
  testDir: "e2e",
  testIgnore: ELSEWHERE,
  forbidOnly: IN_CI,
  reporter: IN_CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PREVIEW_PORT}` },
  projects: stagesToRun().map((stage, index, stages) => {
    const before = stages[index - 1];
    return {
      ...stage,
      dependencies: before === undefined ? [] : [before.name],
      use: { ...devices["Desktop Chrome"] },
    };
  }),
  webServer: [
    {
      command: `${PYTHON} -m greenhouse_sim.api --port ${TEST_SIMULATOR_API_PORT}`,
      url: `${simulatorApi(TEST_SIMULATOR_API_PORT)}/api/health`,
      reuseExistingServer: REUSE_TEST_SERVERS,
    },
    {
      command: `npm run build && npx vite preview --port ${PREVIEW_PORT} --strictPort`,
      url: `http://localhost:${PREVIEW_PORT}`,
      env: { SIMULATOR_API_PORT: String(TEST_SIMULATOR_API_PORT) },
      reuseExistingServer: REUSE_TEST_SERVERS,
    },
  ],
});
