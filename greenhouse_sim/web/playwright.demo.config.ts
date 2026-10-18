import { defineConfig } from "@playwright/test";

import {
  REUSE_TEST_SERVERS,
  simulatorApi,
  simulatorServer,
  TEST_SIMULATOR_API_PORT,
} from "./simulatorApi.ts";

// P09.9's demo video: the final QA's walk-through (`e2e/demo.spec.ts`),
// recorded by Playwright as it plays, on this machine's graphics card, so
// that each release can record it again (`npm run demo:record`). The video
// is written under `test-results/demo/`; uploading it is done by hand
// (docs/demo.md). PYTHON names an interpreter that has greenhouse-sim
// installed (`simulatorServer`).
const PREVIEW_PORT = 4320;
const VIEW = { width: 1280, height: 720 };

export default defineConfig({
  testDir: "e2e",
  testMatch: "demo.spec.ts",
  outputDir: "test-results/demo",
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PREVIEW_PORT}`,
    viewport: VIEW,
    video: { mode: "on", size: VIEW },
    // The full browser, whose headless mode draws on the graphics card.
    channel: "chromium",
  },
  webServer: [
    {
      command: simulatorServer(TEST_SIMULATOR_API_PORT),
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
