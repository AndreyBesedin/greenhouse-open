import type { ReactNode } from "react";

import type { BuildInfo } from "./buildInfo";
import { HomeButton } from "./landing/HomeButton";
import type { PanelTheme } from "./panelTheme";
import { SceneFailures, SceneStatus } from "./SceneStatus";
import { SourceChooser } from "./SourceChooser";
import type { ScenariosState } from "./scenarios";
import type { SceneState } from "./scene/sceneLoad";
import type { SceneSource } from "./scene/source";

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
  theme?: PanelTheme;
  onTheme?: (theme: PanelTheme) => void;
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
            <h1>greenhouse-sim viewer</h1>
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
      {/* What the viewer was built from, last, in a line: QA mode's run
          manifest says it too, beside the simulator's own (#206). */}
      <div className="panel-footer">
        <p className="build-line" data-testid="build-line">
          simulator {build.simulatorVersion} · commit {build.sourceCommit}
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
