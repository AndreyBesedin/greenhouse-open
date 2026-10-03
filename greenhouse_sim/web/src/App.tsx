import { useEffect, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { Hud, type LiveStatus } from "./Hud";
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
import { useLiveScene } from "./scene/useLiveScene";
import { Viewport } from "./Viewport";
import type { Point3 } from "./world";

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const [scene, setScene] = useState<SceneState>({ status: "none" });
  const [presetRequest, setPresetRequest] = useState<PresetRequest | null>(null);
  const [sample, setSample] = useState<ViewSample | null>(null);
  const [pointer, setPointer] = useState<Point3 | null>(null);
  const live = useLiveScene(source.kind === "live" ? source.scenarioId : null);

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
    if (source.kind === "live") {
      return;
    }
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

  const shown = source.kind === "live" ? live.scene : scene;
  const liveStatus: LiveStatus | null =
    source.kind === "live" ? { connection: live.connection, frame: live.frame } : null;

  function choosePreset(preset: PresetName): void {
    setPresetRequest((previous) => ({ preset, serial: (previous?.serial ?? 0) + 1 }));
  }

  return (
    <main className="viewer">
      <Viewport
        snapshot={shown.status === "loaded" ? shown.snapshot : null}
        presetRequest={presetRequest}
        onSample={setSample}
        onPointer={setPointer}
      />
      <InfoPanel
        build={build}
        scenarios={scenarios}
        source={source}
        scene={shown}
        onSource={chooseSource}
      />
      <Hud sample={sample} pointer={pointer} live={liveStatus} onPreset={choosePreset} />
    </main>
  );
}
