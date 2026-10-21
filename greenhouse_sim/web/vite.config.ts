import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import { DEFAULT_SIMULATOR_API_PORT, simulatorApi } from "./simulatorApi.ts";

// The viewer ships with the simulator, so it reports the simulator's version
// rather than keeping a second one in step.
function simulatorVersion(): string {
  const pyproject = readFileSync(new URL("../pyproject.toml", import.meta.url), "utf8");
  const match = /^version\s*=\s*"([^"]+)"/m.exec(pyproject);
  if (!match?.[1]) {
    throw new Error("no version in greenhouse_sim/pyproject.toml");
  }
  return match[1];
}

// The browser tests point the preview at their own API.
const SIMULATOR_API = simulatorApi(
  Number(process.env.SIMULATOR_API_PORT ?? DEFAULT_SIMULATOR_API_PORT),
);

// How much of the handwritten code the unit tests run, in %, at least. The
// 3D drawing, the QA pages and App, which the browser tests run, count as
// not covered. The branches' floor was lowered from 57 when the hand checks
// of the simulator's answers, whose branches the tests ran nearly all of,
// gave way to the generated contracts, which are not counted (AUDIT.8, W12):
// 58.9% of branches before, 55.1% after, with no test taken away.
const COVERED_STATEMENTS_PCT = 65;
const COVERED_BRANCHES_PCT = 55;
const COVERED_FUNCTIONS_PCT = 60;
const COVERED_LINES_PCT = 66;

// Three.js alone is about a megabyte minified. The viewer is a local
// development tool, so a single chunk of this size is fine.
const CHUNK_SIZE_WARNING_KB = 1500;

// The commit the viewer was built from, when built inside a git checkout.
function sourceCommit(): string {
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: CHUNK_SIZE_WARNING_KB },
  // Forward /api to the simulator, so the page and the API share an origin.
  server: { proxy: { "/api": SIMULATOR_API } },
  preview: { proxy: { "/api": SIMULATOR_API } },
  define: {
    __SIMULATOR_VERSION__: JSON.stringify(simulatorVersion()),
    __SOURCE_COMMIT__: JSON.stringify(sourceCommit()),
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
    // Of the handwritten code only: not the contracts generated from the
    // simulator's schemas, the tests, or what the tests are written with.
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/generated/**", "src/testing/**"],
      reporter: ["text-summary"],
      // The baseline measured on 2026-10-11, rounded down (FE-AUDIT.4): no
      // change may lower it unnoticed. Raise them as tests are added.
      thresholds: {
        statements: COVERED_STATEMENTS_PCT,
        branches: COVERED_BRANCHES_PCT,
        functions: COVERED_FUNCTIONS_PCT,
        lines: COVERED_LINES_PCT,
      },
    },
  },
});
