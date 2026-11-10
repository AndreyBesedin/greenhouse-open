import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildInfo, describeBuild } from "./buildInfo";
import type { ScenarioSummary } from "./generated/scenarioSummaryTypes";
import { InfoPanel, viewTitle } from "./InfoPanel";
import { FIRST_LAB_RUN } from "./plants/lab";

const LOADING = { status: "loading" } as const;
const REFERENCE = { kind: "reference" } as const;
const NONE = { status: "none" } as const;
const ignore = () => undefined;
const BUILD = { simulatorVersion: "9.8.7", sourceCommit: "abc1234", sourceBranch: "main" };
const HOUSE = { id: "house", name: "A house" } as ScenarioSummary;

describe("the viewer's information panel", () => {
  it("names what it shows, a simulation or a scene, not the viewer", () => {
    const html = renderToStaticMarkup(
      <InfoPanel
        build={buildInfo}
        scenarios={LOADING}
        source={REFERENCE}
        scene={NONE}
        onSource={ignore}
      />,
    );

    expect(html).toContain("<h1>Test scene</h1>");
    expect(html).not.toContain("greenhouse-sim viewer");
  });

  it("names a scenario simulated by its name, once the scenarios are listed", () => {
    const scenario = { kind: "scenario", scenarioId: "house" } as const;

    expect(viewTitle(scenario, { status: "loaded", scenarios: [HOUSE] })).toBe(
      "Simulation of A house",
    );
    expect(viewTitle(scenario, LOADING)).toBe("Simulation of house");
    expect(viewTitle({ kind: "plants", ...FIRST_LAB_RUN }, LOADING)).toBe("Plant lab");
    expect(viewTitle({ kind: "example" }, LOADING)).toBe("Test scene");
  });

  it("shows the version it was built from, and the commit on hover", () => {
    const html = renderToStaticMarkup(
      <InfoPanel
        build={BUILD}
        scenarios={LOADING}
        source={REFERENCE}
        scene={NONE}
        onSource={ignore}
      />,
    );

    // In one line, at the panel's end, under everything it holds (#206),
    // with the panels' theme beside it when it can be changed (#208).
    expect(html).toContain('title="commit abc1234">simulator 9.8.7</p></div></aside>');
  });

  it("names the branch and the commit only on a branch of its own", () => {
    expect(describeBuild(BUILD)).toBe("simulator 9.8.7");
    expect(describeBuild({ ...BUILD, sourceBranch: "HEAD" })).toBe("simulator 9.8.7");
    expect(describeBuild({ ...BUILD, sourceBranch: "unknown" })).toBe("simulator 9.8.7");
    expect(describeBuild({ ...BUILD, sourceBranch: "feat/a-panel" })).toBe(
      "simulator 9.8.7 · feat/a-panel at abc1234",
    );
  });

  it("reports the version of the simulator it ships with", () => {
    const pyproject = readFileSync(new URL("../../pyproject.toml", import.meta.url), "utf8");

    expect(pyproject).toContain(`version = "${buildInfo.simulatorVersion}"`);
  });
});
