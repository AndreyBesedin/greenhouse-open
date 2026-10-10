import { defineConfig, devices } from "@playwright/test";

import { SIMULATOR_API, SIMULATOR_API_PORT } from "./simulatorApi.ts";

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
// P07's final QA works the climate through a whole day, so it runs on its
// own, last, and slows none of the others.
const WEATHER_DAY = "weather-day.spec.ts";
// P08's checks of the sun's light work climate runs out to noon, so they too
// run on their own, once the others and P00's pass, and P07's after them.
const SUN = ["light.spec.ts", "solar-lab.spec.ts"];

export default defineConfig({
  testDir: "e2e",
  testIgnore: ELSEWHERE,
  forbidOnly: IN_CI,
  reporter: IN_CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PREVIEW_PORT}` },
  projects: [
    {
      name: "chromium",
      testIgnore: [...ELSEWHERE, RENDERER_SMOKE, WEATHER_DAY, ...SUN],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "renderer-smoke",
      testMatch: RENDERER_SMOKE,
      dependencies: ["chromium"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "sun",
      testMatch: SUN,
      dependencies: ["renderer-smoke"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "weather-day",
      testMatch: WEATHER_DAY,
      dependencies: ["sun"],
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `${PYTHON} -m greenhouse_sim.api --port ${SIMULATOR_API_PORT}`,
      url: `${SIMULATOR_API}/api/health`,
      reuseExistingServer: !IN_CI,
    },
    {
      command: `npm run build && npx vite preview --port ${PREVIEW_PORT} --strictPort`,
      url: `http://localhost:${PREVIEW_PORT}`,
      reuseExistingServer: !IN_CI,
    },
  ],
});
