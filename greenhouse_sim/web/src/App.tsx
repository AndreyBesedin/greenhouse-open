import { useEffect, useMemo, useRef, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { DisplayOptions } from "./DisplayOptions";
import { CategoryLegend } from "./debug/CategoryLegend";
import { categoriesIn } from "./debug/categories";
import { sceneDimensionOverlays } from "./debug/dimensions";
import { ALL_OVERLAYS, type OverlayToggles, selectionOverlays } from "./debug/overlays";
import { ScalarLegend } from "./debug/ScalarLegend";
import { colouringBy, scalarProperties } from "./debug/scalar";
import { Hud, type LiveStatus } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import { Inspector } from "./Inspector";
import { OpeningControls } from "./OpeningControls";
import { PLANT_LAB_POSE } from "./plants/lab";
import { PlantStructure } from "./plants/PlantStructure";
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
  // Only the latest command in the current source may update its feedback.
  const commandGeneration = useRef(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overlayToggles, setOverlayToggles] = useState<OverlayToggles>(ALL_OVERLAYS);
  const [colourBy, setColourBy] = useState<string | null>(null);
  const [showDimensions, setShowDimensions] = useState(false);
  const [byCategory, setByCategory] = useState(false);
  // Which scenario's scene is on show, so reopening it does not blank it.
  const shownScenario = useRef<string | null>(null);
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

  // A command answered after the viewer has gone has no feedback to give.
  useEffect(
    () => () => {
      commandGeneration.current += 1;
    },
    [],
  );

  useEffect(() => {
    if (source.kind === "live") {
      return;
    }
    let current = true;
    // A scenario reopened by its sliders keeps its scene on show until the
    // next arrives; any other change of scene starts from loading.
    const sameScenario = source.kind === "scenario" && source.scenarioId === shownScenario.current;
    shownScenario.current = source.kind === "scenario" ? source.scenarioId : null;
    setScene((previous) =>
      source.kind === "reference"
        ? { status: "none" }
        : sameScenario && previous.status === "loaded"
          ? previous
          : { status: "loading" },
    );
    void loadScene(source).then((state) => {
      if (current) {
        setScene(state);
      }
    });
    return () => {
      current = false;
    };
  }, [source]);

  function setOpenings(openings: Record<string, number>): void {
    if (source.kind !== "scenario") {
      return;
    }
    const next: SceneSource = { ...source, openings };
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  function chooseSource(next: SceneSource): void {
    commandGeneration.current += 1;
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
    const generation = ++commandGeneration.current;
    void sendLiveCommand(liveScenario, next).then((result) => {
      if (generation === commandGeneration.current) {
        setCommandProblem(result.ok ? null : result.problem);
      }
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
        showBounds={showDimensions}
        byCategory={byCategory}
        initialPose={source.kind === "plants" ? PLANT_LAB_POSE : null}
        onSample={setSample}
        onPointer={setPointer}
        onSelect={setSelectedId}
      />
      <div className="viewer-panels">
        <div className="panel-column">
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
                byCategory={byCategory}
                onByCategory={setByCategory}
              />
            )}
            {snapshot !== null && source.kind === "scenario" && (
              <OpeningControls
                snapshot={snapshot}
                requested={source.openings ?? {}}
                onChange={setOpenings}
              />
            )}
            {source.kind === "plants" && (
              <PlantStructure selectedId={selectedId} onSelect={setSelectedId} />
            )}
          </InfoPanel>
          {selected && (
            <Inspector
              entity={selected}
              overlays={overlayToggles}
              onOverlays={setOverlayToggles}
              onClear={() => setSelectedId(null)}
            />
          )}
        </div>
        <div className="panel-column at-the-end">
          <Hud
            sample={sample}
            pointer={pointer}
            live={liveStatus}
            onPreset={choosePreset}
            onCommand={command}
          />
          <div className="legends">
            {byCategory && snapshot !== null && (
              <CategoryLegend categories={categoriesIn(snapshot)} />
            )}
            {colouring && <ScalarLegend colouring={colouring} />}
          </div>
        </div>
      </div>
    </main>
  );
}
