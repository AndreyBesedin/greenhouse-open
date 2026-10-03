import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

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
  define: {
    __SIMULATOR_VERSION__: JSON.stringify(simulatorVersion()),
    __SOURCE_COMMIT__: JSON.stringify(sourceCommit()),
  },
  test: {
    environment: "node",
  },
});
