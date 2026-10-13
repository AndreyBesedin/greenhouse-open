import { defineConfig } from "@playwright/test";

import { REUSE_TEST_SERVERS, simulatorApi, TEST_SIMULATOR_API_PORT } from "./simulatorApi.ts";

// The renderer's performance benchmarks, measured on this machine's graphics
// card: the stress scene, and the reference greenhouse at its fullest crop,
// which its own API works out (P09.8). They are a record, not a gate: they
// never fail on the numbers, and CI, which has no graphics card, does not run
// them. PYTHON names an interpreter that has greenhouse-sim installed.
const PYTHON = process.env.PYTHON ?? "python";
const PREVIEW_PORT = 4319;
// Several scenes, each loaded, warmed up and orbited for seconds; the
// reference greenhouse's sets its own, longer.
const BENCHMARK_TIMEOUT_MS = 180_000;

export default defineConfig({
  testDir: "e2e/bench",
  testMatch: "*.bench.ts",
  timeout: BENCHMARK_TIMEOUT_MS,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PREVIEW_PORT}`,
    viewport: { width: 1280, height: 720 },
    // The full browser, whose headless mode draws on the graphics card; the
    // default headless shell draws in software. Without the frame rate tied
    // to the display, the frame time measures the work, not the refresh.
    channel: "chromium",
    launchOptions: { args: ["--disable-gpu-vsync", "--disable-frame-rate-limit"] },
  },
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
