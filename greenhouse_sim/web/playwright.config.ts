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
// The plant lab grows a row of thousands of entities on its later days, and
// times out when the climate's runs share the simulator with it: it runs on
// its own, once the others and P00's pass.
const PLANT_LAB = "plant-lab.spec.ts";
// P07's final QA works the climate through a whole day, so it runs on its
// own too, after the plant lab, and slows none of them.
const WEATHER_DAY = "weather-day.spec.ts";

export default defineConfig({
  testDir: "e2e",
  testIgnore: ELSEWHERE,
  forbidOnly: IN_CI,
  reporter: IN_CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PREVIEW_PORT}` },
  projects: [
    {
      name: "chromium",
      testIgnore: [...ELSEWHERE, RENDERER_SMOKE, PLANT_LAB, WEATHER_DAY],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "renderer-smoke",
      testMatch: RENDERER_SMOKE,
      dependencies: ["chromium"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "plant-lab",
      testMatch: PLANT_LAB,
      dependencies: ["renderer-smoke"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "weather-day",
      testMatch: WEATHER_DAY,
      dependencies: ["plant-lab"],
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
