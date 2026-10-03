import { useEffect, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import { ScenarioList } from "./ScenarioList";
import { loadScenarios, type ScenariosState } from "./scenarios";

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });

  useEffect(() => {
    let current = true;
    void loadScenarios().then((state) => {
      if (current) {
        setScenarios(state);
      }
    });
    return () => {
      current = false;
    };
  }, []);

  return (
    <main>
      <h1>greenhouse-sim viewer</h1>
      <dl>
        <dt>Simulator version</dt>
        <dd>{build.simulatorVersion}</dd>
        <dt>Built from commit</dt>
        <dd>{build.sourceCommit}</dd>
      </dl>
      <ScenarioList state={scenarios} />
    </main>
  );
}
