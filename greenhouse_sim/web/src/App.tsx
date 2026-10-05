import { useEffect, useMemo, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { DisplayOptions } from "./DisplayOptions";
import { sceneDimensionOverlays } from "./debug/dimensions";
import { ALL_OVERLAYS, type OverlayToggles, selectionOverlays } from "./debug/overlays";
import { ScalarLegend } from "./debug/ScalarLegend";
import { colouringBy, scalarProperties } from "./debug/scalar";
import { Hud, type LiveStatus } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import { Inspector } from "./Inspector";
import type { ViewSample } from "./readouts";
import { loadScenarios, type ScenariosState } from "./scenarios";
import { type LiveCommand, sendLiveCommand } from "./scene/live";
import {
  loadScene,
  type SceneSource,
  type SceneState,
  searchFor,
  sourceFromSearch,
} from "./scene/source";
import { useLiveScene } from "./scene/useLiveScene";
import { selectedEntity } from "./selection";
import { Viewport } from "./Viewport";
import type { Point3 } from "./world";

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const [scene, setScene] = useState<SceneState>({ status: "none" });
  const [presetRequest, setPresetRequest] = useState<PresetRequest | null>(null);
  const [sample, setSample] = useState<ViewSample | null>(null);
  const [pointer, setPointer] = useState<Point3 | null>(null);
  const [commandProblem, setCommandProblem] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overlayToggles, setOverlayToggles] = useState<OverlayToggles>(ALL_OVERLAYS);
  const [colourBy, setColourBy] = useState<string | null>(null);
  const [showDimensions, setShowDimensions] = useState(false);
  const liveScenario = source.kind === "live" ? source.scenarioId : null;
  const live = useLiveScene(liveScenario);

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
    setCommandProblem(null);
    setSelectedId(null);
    setColourBy(null);
  }

  function command(next: LiveCommand): void {
    if (liveScenario === null) {
      return;
    }
    void sendLiveCommand(liveScenario, next).then((result) => {
      setCommandProblem(result.ok ? null : result.problem);
    });
  }

  const shown = source.kind === "live" ? live.scene : scene;
  const snapshot = shown.status === "loaded" ? shown.snapshot : null;
  // Overlays and colours are worked out from the scene, which they only read.
  const selected = selectedEntity(snapshot, selectedId);
  const overlays = useMemo(
    () => [
      ...(selected === null ? [] : selectionOverlays(selected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
    ],
    [selected, overlayToggles, snapshot, showDimensions],
  );
  const colourProperties = useMemo(
    () => (snapshot === null ? [] : scalarProperties(snapshot)),
    [snapshot],
  );
  const colouring = useMemo(
    () => (snapshot === null || colourBy === null ? null : colouringBy(snapshot, colourBy)),
    [snapshot, colourBy],
  );
  const liveStatus: LiveStatus | null =
    source.kind === "live"
      ? { connection: live.connection, frame: live.frame, problem: commandProblem }
      : null;

  function choosePreset(preset: PresetName): void {
    setPresetRequest((previous) => ({ preset, serial: (previous?.serial ?? 0) + 1 }));
  }

  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={presetRequest}
        selectedId={selectedId}
        colouring={colouring}
        overlays={overlays}
        onSample={setSample}
        onPointer={setPointer}
        onSelect={setSelectedId}
      />
      <InfoPanel
        build={build}
        scenarios={scenarios}
        source={source}
        scene={shown}
        onSource={chooseSource}
      >
        {snapshot !== null && (
          <DisplayOptions
            colourProperties={colourProperties}
            colourBy={colourBy}
            onColourBy={setColourBy}
            showDimensions={showDimensions}
            onShowDimensions={setShowDimensions}
          />
        )}
      </InfoPanel>
      <Hud
        sample={sample}
        pointer={pointer}
        live={liveStatus}
        onPreset={choosePreset}
        onCommand={command}
      />
      {selected && (
        <Inspector
          entity={selected}
          overlays={overlayToggles}
          onOverlays={setOverlayToggles}
          onClear={() => setSelectedId(null)}
        />
      )}
      {colouring && <ScalarLegend colouring={colouring} />}
    </main>
  );
}
