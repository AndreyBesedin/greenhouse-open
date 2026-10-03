import type { BuildInfo } from "./buildInfo";
import { ScenarioList } from "./ScenarioList";
import { SceneStatus } from "./SceneStatus";
import type { ScenariosState } from "./scenarios";
import type { SceneSource, SceneState } from "./scene/source";

export function InfoPanel({
  build,
  scenarios,
  source,
  scene,
  onSource,
}: {
  build: BuildInfo;
  scenarios: ScenariosState;
  source: SceneSource;
  scene: SceneState;
  onSource: (source: SceneSource) => void;
}) {
  return (
    <aside className="info-panel">
      <h1>greenhouse-sim viewer</h1>
      <dl>
        <dt>Simulator version</dt>
        <dd>{build.simulatorVersion}</dd>
        <dt>Built from commit</dt>
        <dd>{build.sourceCommit}</dd>
      </dl>
      <SceneStatus source={source} state={scene} />
      <p>
        <button type="button" onClick={() => onSource({ kind: "reference" })}>
          Reference scene
        </button>{" "}
        <button type="button" onClick={() => onSource({ kind: "example" })}>
          Example scene
        </button>
      </p>
      <ScenarioList
        state={scenarios}
        onShow={(scenarioId) => onSource({ kind: "scenario", scenarioId })}
        onLive={(scenarioId) => onSource({ kind: "live", scenarioId })}
      />
    </aside>
  );
}
