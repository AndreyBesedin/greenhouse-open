import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The simulator's local API (`python -m greenhouse_sim.api`). The dev and
// preview servers forward /api to it, so the page and the API share an origin.
const SIMULATOR_API = "http://127.0.0.1:8765";

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
  server: { proxy: { "/api": SIMULATOR_API } },
  preview: { proxy: { "/api": SIMULATOR_API } },
  define: {
    __SIMULATOR_VERSION__: JSON.stringify(simulatorVersion()),
    __SOURCE_COMMIT__: JSON.stringify(sourceCommit()),
  },
  test: {
    environment: "node",
  },
});
