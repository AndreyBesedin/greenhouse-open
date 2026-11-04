import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig } from "@playwright/test";

import {
  REUSE_TEST_SERVERS,
  simulatorApi,
  simulatorServer,
  TEST_SIMULATOR_API_PORT,
  testPort,
} from "./simulatorApi.ts";

// The README's demo video: the short walk-through (`e2e/demo.spec.ts`),
// recorded by Playwright as it plays, on this machine's graphics card, so
// that a release can record it again (`npm run demo:record`). The video is
// written under `test-results/demo/`, where `uv run record-demo` cuts it for
// the README; uploading it is done by hand (docs/demo.md). PYTHON names an
// interpreter that has greenhouse-sim installed (`simulatorServer`).
// Its preview's port, unless TEST_PORT_OFFSET moves it.
const OWN_PREVIEW_PORT = 4320;
const PREVIEW_PORT = testPort(OWN_PREVIEW_PORT);
const VIEW = { width: 1280, height: 720 };
// The walk-through to record: DEMO_SPEC, to record the long one (docs/demo.md).
const WALK_THROUGH = process.env.DEMO_SPEC ?? "demo.spec.ts";
// What is recorded is kept in a folder of its own, never the user's: their runs
// and drafts are not for a video. DEMO_STORE names one to keep between
// recordings, with the run the walk-through replays already computed in it.
const STORE = process.env.DEMO_STORE ?? mkdtempSync(join(tmpdir(), "greenhouse-sim-demo-"));

export default defineConfig({
  testDir: "e2e",
  testMatch: WALK_THROUGH,
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
      command: simulatorServer(TEST_SIMULATOR_API_PORT, undefined, join(STORE, "drafts.sqlite3")),
      url: `${simulatorApi(TEST_SIMULATOR_API_PORT)}/api/health`,
      env: { XDG_STATE_HOME: STORE },
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
