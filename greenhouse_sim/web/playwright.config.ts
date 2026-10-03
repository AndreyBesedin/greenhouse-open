import { defineConfig, devices } from "@playwright/test";

import { SIMULATOR_API, SIMULATOR_API_PORT } from "./simulatorApi.ts";

// The smoke test runs the real thing: the simulator's local API and the
// production build of the viewer, in Chromium. PYTHON names an interpreter
// that has greenhouse-sim installed.
const PYTHON = process.env.PYTHON ?? "python";
const PREVIEW_PORT = 4317;
const IN_CI = process.env.CI !== undefined;

export default defineConfig({
  testDir: "e2e",
  forbidOnly: IN_CI,
  reporter: IN_CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PREVIEW_PORT}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
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
