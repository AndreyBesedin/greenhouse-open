import { useEffect, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import { InfoPanel } from "./InfoPanel";
import { ReferenceScene } from "./ReferenceScene";
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
    <main className="viewer">
      <ReferenceScene />
      <InfoPanel build={build} scenarios={scenarios} />
    </main>
  );
}
