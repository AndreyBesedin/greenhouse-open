import type { ReactNode } from "react";

import type { BuildInfo } from "./buildInfo";
import { DEFAULT_STRESS_PLANTS } from "./qa/stressScene";
import { ScenarioList } from "./ScenarioList";
import { SceneStatus } from "./SceneStatus";
import { DEFAULT_LAYOUT, type ScenariosState } from "./scenarios";
import type { SceneSource, SceneState } from "./scene/source";

export function InfoPanel({
  build,
  scenarios,
  source,
  scene,
  onSource,
  children,
}: {
  build: BuildInfo;
  scenarios: ScenariosState;
  source: SceneSource;
  scene: SceneState;
  onSource: (source: SceneSource) => void;
  /** Display options for the scene, shown under its choice. */
  children?: ReactNode;
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
        </button>{" "}
        <button type="button" onClick={() => onSource({ kind: "fixtures" })}>
          Fixture gallery
        </button>{" "}
        <button type="button" onClick={() => onSource({ kind: "plants" })}>
          Plant lab
        </button>{" "}
        <button
          type="button"
          onClick={() => onSource({ kind: "stress", plants: DEFAULT_STRESS_PLANTS })}
        >
          Stress scene
        </button>
      </p>
      {children}
      <ScenarioList
        state={scenarios}
        shownLayout={
          source.kind === "scenario"
            ? { scenarioId: source.scenarioId, layout: source.layout ?? DEFAULT_LAYOUT }
            : null
        }
        onShow={(scenarioId, layout = DEFAULT_LAYOUT) =>
          onSource({
            kind: "scenario",
            scenarioId,
            ...(layout === DEFAULT_LAYOUT ? {} : { layout }),
          })
        }
        onLive={(scenarioId) => onSource({ kind: "live", scenarioId })}
      />
    </aside>
  );
}
