import { useEffect, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { Hud } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import type { ViewSample } from "./readouts";
import { loadScenarios, type ScenariosState } from "./scenarios";
import {
  loadScene,
  type SceneSource,
  type SceneState,
  searchFor,
  sourceFromSearch,
} from "./scene/source";
import { Viewport } from "./Viewport";
import type { Point3 } from "./world";

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const [scene, setScene] = useState<SceneState>({ status: "none" });
  const [presetRequest, setPresetRequest] = useState<PresetRequest | null>(null);
  const [sample, setSample] = useState<ViewSample | null>(null);
  const [pointer, setPointer] = useState<Point3 | null>(null);

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

  useEffect(() => {
    let current = true;
    setScene(source.kind === "reference" ? { status: "none" } : { status: "loading" });
    void loadScene(source).then((state) => {
      if (current) {
        setScene(state);
      }
    });
    return () => {
      current = false;
    };
  }, [source]);

  function chooseSource(next: SceneSource): void {
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  function choosePreset(preset: PresetName): void {
    setPresetRequest((previous) => ({ preset, serial: (previous?.serial ?? 0) + 1 }));
  }

  return (
    <main className="viewer">
      <Viewport
        snapshot={scene.status === "loaded" ? scene.snapshot : null}
        presetRequest={presetRequest}
        onSample={setSample}
        onPointer={setPointer}
      />
      <InfoPanel
        build={build}
        scenarios={scenarios}
        source={source}
        scene={scene}
        onSource={chooseSource}
      />
      <Hud sample={sample} pointer={pointer} onPreset={choosePreset} />
    </main>
  );
}
