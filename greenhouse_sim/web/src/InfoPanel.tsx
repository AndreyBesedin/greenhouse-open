import type { BuildInfo } from "./buildInfo";
import { ScenarioList } from "./ScenarioList";
import type { ScenariosState } from "./scenarios";

export function InfoPanel({ build, scenarios }: { build: BuildInfo; scenarios: ScenariosState }) {
  return (
    <aside className="info-panel">
      <h1>greenhouse-sim viewer</h1>
      <dl>
        <dt>Simulator version</dt>
        <dd>{build.simulatorVersion}</dd>
        <dt>Built from commit</dt>
        <dd>{build.sourceCommit}</dd>
      </dl>
      <ScenarioList state={scenarios} />
    </aside>
  );
}
