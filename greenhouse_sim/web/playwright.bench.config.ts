import { defineConfig } from "@playwright/test";

// The renderer's performance benchmark: the stress scene, measured on this
// machine's graphics card. It is a record, not a gate: it never fails on the
// numbers, and CI, which has no graphics card, does not run it.
const PREVIEW_PORT = 4319;
// Several scenes, each loaded, warmed up and orbited for seconds.
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
  webServer: {
    command: `npm run build && npx vite preview --port ${PREVIEW_PORT} --strictPort`,
    url: `http://localhost:${PREVIEW_PORT}`,
    reuseExistingServer: true,
  },
});
