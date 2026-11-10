import type { ReactNode } from "react";

import { type BuildInfo, describeBuild } from "./buildInfo";
import type { Theme } from "./design/theme";
import { HomeButton } from "./landing/HomeButton";
import { SceneFailures, SceneStatus } from "./SceneStatus";
import { SourceChooser } from "./SourceChooser";
import type { ScenariosState } from "./scenarios";
import type { SceneState } from "./scene/sceneLoad";
import type { SceneSource } from "./scene/source";

/** What the viewer shows, as its heading names it (P22.8): a scenario simulated
 * here, by its name, the plant lab, or a scene drawn to check the renderer. A run
 * the simulator keeps is a replay's, whose own header names it. */
export function viewTitle(source: SceneSource, scenarios: ScenariosState): string {
  switch (source.kind) {
    case "scenario": {
      const summary =
        scenarios.status === "loaded"
          ? scenarios.scenarios.find((scenario) => scenario.id === source.scenarioId)
          : undefined;
      return `Simulation of ${summary?.name ?? source.scenarioId}`;
    }
    case "plants":
      return "Plant lab";
    default:
      return "Test scene";
  }
}

export function InfoPanel({
  build,
  scenarios,
  source,
  scene,
  failures = [],
  chooseFirst = false,
  embedded = false,
  theme = "dark",
  onTheme,
  onSource,
  children,
}: {
  build: BuildInfo;
  scenarios: ScenariosState;
  source: SceneSource;
  scene: SceneState;
  /** What failed to arrive while something else is drawn in its place. */
  failures?: readonly string[];
  /** Whether nothing has been chosen yet, so that the choice starts open. */
  chooseFirst?: boolean;
  /** Whether a page of its own holds the viewer (a replay's): it has its own
   * way home, and no other scene is chosen, for it would not be the run. */
  embedded?: boolean;
  /** How the panels look, and how to change it (#208), if they can be. */
  theme?: Theme;
  onTheme?: (theme: Theme) => void;
  onSource: (source: SceneSource) => void;
  /** Display options for the scene, shown under its choice. */
  children?: ReactNode;
}) {
  return (
    <aside className="info-panel">
      {embedded ? (
        // A scene on its way, or one that could not be drawn, still says so.
        <SceneStatus source={source} state={scene} />
      ) : (
        <>
          <div className="panel-head">
            <HomeButton />
            <h1>{viewTitle(source, scenarios)}</h1>
          </div>
          <SourceChooser
            scenarios={scenarios}
            source={source}
            scene={scene}
            initiallyOpen={chooseFirst}
            onSource={onSource}
          />
        </>
      )}
      <SceneFailures failures={failures} />
      {children}
      {/* What the viewer was built from, last, in a line, its commit on hover:
          QA mode's run manifest says it too, beside the simulator's own (#206). */}
      <div className="panel-footer">
        <p className="build-line" data-testid="build-line" title={`commit ${build.sourceCommit}`}>
          {describeBuild(build)}
        </p>
        {onTheme !== undefined && (
          <label className="panel-theme">
            <input
              type="checkbox"
              checked={theme === "light"}
              onChange={(event) => onTheme(event.target.checked ? "light" : "dark")}
            />{" "}
            Light panels
          </label>
        )}
      </div>
    </aside>
  );
}
