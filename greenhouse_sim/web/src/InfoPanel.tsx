import type { ReactNode } from "react";

import type { BuildInfo } from "./buildInfo";
import { SceneFailures } from "./SceneStatus";
import { SourceChooser } from "./SourceChooser";
import type { ScenariosState } from "./scenarios";
import type { SceneSource, SceneState } from "./scene/source";

export function InfoPanel({
  build,
  scenarios,
  source,
  scene,
  failures = [],
  chooseFirst = false,
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
  onSource: (source: SceneSource) => void;
  /** Display options for the scene, shown under its choice. */
  children?: ReactNode;
}) {
  return (
    <aside className="info-panel">
      <h1>greenhouse-sim viewer</h1>
      <SourceChooser
        scenarios={scenarios}
        source={source}
        scene={scene}
        initiallyOpen={chooseFirst}
        onSource={onSource}
      />
      <SceneFailures failures={failures} />
      {children}
      {/* What the viewer was built from, last, in a line: QA mode's run
          manifest says it too, beside the simulator's own (#206). */}
      <p className="build-line" data-testid="build-line">
        simulator {build.simulatorVersion} · commit {build.sourceCommit}
      </p>
    </aside>
  );
}
