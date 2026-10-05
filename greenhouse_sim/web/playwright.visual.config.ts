import { defineConfig, devices } from "@playwright/test";

// Screenshot regression for the renderer (decision 0014). The baselines are
// drawn in CI's container, mcr.microsoft.com/playwright:v1.63.0-noble-amd64,
// whose fonts and software renderer draw the same pixels on every run.
// Elsewhere the comparisons are skipped. The QA page needs only the built
// viewer, not the simulator.
const PREVIEW_PORT = 4318;
const IN_CI = process.env.CI !== undefined;
// A pixel counts as different when its colour moves more than this, on
// Playwright's 0-to-1 scale; smaller moves are edge smoothing.
const PIXEL_THRESHOLD = 0.2;
// A screenshot fails when more pixels than this differ, about 0.01% of the
// 1280 by 720 view. Moving one stem of the QA scene by its own width (6 cm)
// changes about 200 pixels and fails; half that passes.
const MAX_DIFF_PIXELS = 100;

export default defineConfig({
  testDir: "e2e/visual",
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}-{platform}{ext}",
  // A comparison never overwrites a baseline unless asked to
  // (--update-snapshots). A missing one is drawn into the test's results and
  // the test fails, which is how CI hands over a first baseline.
  updateSnapshots: "missing",
  expect: {
    toHaveScreenshot: { threshold: PIXEL_THRESHOLD, maxDiffPixels: MAX_DIFF_PIXELS },
  },
  forbidOnly: IN_CI,
  reporter: IN_CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PREVIEW_PORT}` },
  // Desktop Chrome is a 1280 by 720 view at one device pixel per CSS pixel.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && npx vite preview --port ${PREVIEW_PORT} --strictPort`,
    url: `http://localhost:${PREVIEW_PORT}`,
    reuseExistingServer: !IN_CI,
  },
});
