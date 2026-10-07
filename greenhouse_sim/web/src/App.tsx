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
import { FieldArrows } from "./fields/FieldArrows";
import { FieldControls } from "./fields/FieldControls";
import { type FieldState, loadField } from "./fields/source";
import { Hud, type LiveStatus } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import { Inspector } from "./Inspector";
import { OpeningControls } from "./OpeningControls";
import { type GrowthSpeed, LabControls } from "./plants/LabControls";
import {
  type LabRun,
  PLANT_LAB_FIRST_PLANT,
  PLANT_LAB_LAST_DAY,
  PLANT_LAB_POSE,
} from "./plants/lab";
import { plantNameOverlays } from "./plants/names";
import { PlantActions } from "./plants/PlantActions";
import { PlantStructure } from "./plants/PlantStructure";
import { RuleChecks } from "./plants/RuleChecks";
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
import { entityOfOrgan, organOf, plantOf, selectedEntity } from "./selection";
import { Viewport } from "./Viewport";
import type { Point3 } from "./world";

const MILLISECONDS_PER_SECOND = 1000;

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const [scene, setScene] = useState<SceneState>({ status: "none" });
  const [field, setField] = useState<FieldState>({ status: "none" });
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
  // The plant lab's play, its speed in days a second, and its plants' names.
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<GrowthSpeed>(1);
  const [showPlantNames, setShowPlantNames] = useState(false);
  // Which scenario's scene, or the plant lab's, is on show, so reopening it
  // does not blank it.
  const shownView = useRef<string | null>(null);
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
    // A scenario reopened by its sliders, or the plant lab on another day,
    // keeps its scene on show until the next arrives; any other change of
    // scene starts from loading.
    const view =
      source.kind === "scenario"
        ? `scenario ${source.scenarioId}`
        : source.kind === "plants"
          ? "plants"
          : null;
    const sameView = view !== null && view === shownView.current;
    shownView.current = view;
    setScene((previous) =>
      source.kind === "reference"
        ? { status: "none" }
        : sameView && previous.status === "loaded"
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

  // The scenario's field, drawn over its scene, loaded whenever another is
  // chosen; the last one stays on show until the next arrives.
  const fieldScenario = source.kind === "scenario" ? source.scenarioId : null;
  const fieldName = source.kind === "scenario" ? (source.field ?? null) : null;
  useEffect(() => {
    if (fieldScenario === null || fieldName === null) {
      setField({ status: "none" });
      return;
    }
    let current = true;
    setField((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadField(fieldScenario, fieldName).then((state) => {
      if (current) {
        setField(state);
      }
    });
    return () => {
      current = false;
    };
  }, [fieldScenario, fieldName]);

  function chooseField(name: string | null): void {
    if (source.kind !== "scenario") {
      return;
    }
    const { field: _, ...rest } = source;
    const next: SceneSource = name === null ? rest : { ...rest, field: name };
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  function setOpenings(openings: Record<string, number>): void {
    if (source.kind !== "scenario") {
      return;
    }
    const next: SceneSource = { ...source, openings };
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  // A selection is kept from one run of the lab to the next: its organ is the
  // same organ, of the plant in the same place.
  function setLabRun(change: Partial<LabRun>): void {
    if (source.kind !== "plants") {
      return;
    }
    const next: SceneSource = { ...source, ...change };
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  function chooseSource(next: SceneSource): void {
    commandGeneration.current += 1;
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
    setCommandProblem(null);
    setSelectedId(null);
    setPlaying(false);
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
  const showingNames = source.kind === "plants" && showPlantNames;
  const overlays = useMemo(
    () => [
      ...(selected === null ? [] : selectionOverlays(selected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames ? plantNameOverlays(snapshot) : []),
    ],
    [selected, overlayToggles, snapshot, showDimensions, showingNames],
  );

  // Playing, the lab moves on a day once the day asked for is on show, at
  // most as fast as its speed, and stops on its last day.
  const labDay = source.kind === "plants" ? source.day : null;
  const shownDay = snapshot === null ? null : snapshot.simulated_day;
  useEffect(() => {
    if (!playing || labDay === null || shownDay !== labDay) {
      return;
    }
    if (labDay >= PLANT_LAB_LAST_DAY) {
      setPlaying(false);
      return;
    }
    const next = window.setTimeout(() => {
      setSource((current) => {
        if (current.kind !== "plants") {
          return current;
        }
        const later: SceneSource = { ...current, day: labDay + 1 };
        history.replaceState(null, "", `${location.pathname}${searchFor(later)}`);
        return later;
      });
    }, MILLISECONDS_PER_SECOND / speed);
    return () => window.clearTimeout(next);
  }, [playing, labDay, shownDay, speed]);
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
      >
        {field.status === "loaded" && <FieldArrows field={field.field} />}
      </Viewport>
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
            {source.kind === "scenario" && (
              <FieldControls
                scenarioId={source.scenarioId}
                chosen={source.field ?? null}
                state={field}
                onChoose={chooseField}
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
              <LabControls
                run={source}
                shownDay={shownDay}
                onChange={setLabRun}
                playing={playing}
                speed={speed}
                showNames={showPlantNames}
                onPlaying={setPlaying}
                onSpeed={setSpeed}
                onShowNames={setShowPlantNames}
              />
            )}
            {source.kind === "plants" && <RuleChecks run={source} />}
            {source.kind === "plants" && (
              <PlantActions
                entity={selected}
                day={source.day}
                scheduled={source.actions.length}
                onAct={(action) => setLabRun({ actions: [...source.actions, action] })}
                onUndo={() => setLabRun({ actions: source.actions.slice(0, -1) })}
                onClear={() => setLabRun({ actions: [] })}
              />
            )}
            {source.kind === "plants" && (
              <PlantStructure
                plant={{ ...source, plantId: plantOf(selected) ?? PLANT_LAB_FIRST_PLANT }}
                selectedOrgan={selected === null ? null : organOf(selected)}
                onSelect={(organId) => setSelectedId(entityOfOrgan(snapshot, organId))}
              />
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
