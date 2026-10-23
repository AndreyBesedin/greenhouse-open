import { useCallback, useEffect, useMemo, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import { ControlsHelp } from "./ControlsHelp";
import { type CameraPose, framing, type PresetName, type PresetRequest } from "./camera";
import { CfdBoundaries } from "./cfd/CfdBoundaries";
import { CfdLegend } from "./cfd/CfdLegend";
import { useCfdBoundaries } from "./cfd/useCfdBoundaries";
import { DisplayOptions } from "./DisplayOptions";
import { CategoryLegend } from "./debug/CategoryLegend";
import { categoriesIn } from "./debug/categories";
import { sceneDimensionOverlays } from "./debug/dimensions";
import {
  ALL_OVERLAYS,
  type OverlayToggles,
  sceneOverlaysDrawn,
  selectionOverlays,
  shownPrimitives,
} from "./debug/overlays";
import { ScalarLegend } from "./debug/ScalarLegend";
import { colouringBy, scalarProperties } from "./debug/scalar";
import { arrowSpacing } from "./fields/arrows";
import { FieldArrows } from "./fields/FieldArrows";
import { FieldLegend } from "./fields/FieldLegend";
import { FieldSlice } from "./fields/FieldSlice";
import { FieldStreamlines } from "./fields/FieldStreamlines";
import { withGlazing } from "./fields/glazing";
import { openingFlowOverlays, withOpeningFlows } from "./fields/openingFlows";
import { MAX_PROBES, probeOverlays } from "./fields/probes";
import { CLIMATE_FIELD } from "./fields/source";
import { useClimateLoads } from "./fields/useClimateLoads";
import { useFieldDrawing } from "./fields/useFieldDrawing";
import { Hud, type LiveStatus } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import { Inspector } from "./Inspector";
import { type MoveDraft, MovePanel } from "./MovePanel";
import { PlaybackPanel } from "./PlaybackPanel";
import { usePanelTheme } from "./panelTheme";
import { withCrop } from "./plants/crop";
import type { GrowthSpeed } from "./plants/LabControls";
import { LabPanels } from "./plants/LabPanels";
import { type LabRun, PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "./plants/lab";
import { describePlantLight } from "./plants/light";
import { plantNameOverlays } from "./plants/names";
import { PlantDays } from "./plants/PlantDays";
import { PlantLight } from "./plants/PlantLight";
import { usePlantLoads } from "./plants/usePlantLoads";
import { useQaMode } from "./qaMode/mode";
import { QaPanel } from "./qaMode/QaPanel";
import { useQaLoads } from "./qaMode/useQaLoads";
import type { ViewSample } from "./readouts";
import { ScenarioPanels } from "./ScenarioPanels";
import { WhatAmISeeing, worldAxesLength } from "./SeenInTheView";
import { DEFAULT_LAYOUT, loadScenarios, ownDaily, SCENARIOS_URL } from "./scenarios";
import { withProbes, withTargets, withTargetsSet, withTime } from "./scene/edits";
import { runningThermostat } from "./scene/equipment";
import type { SceneEntity } from "./scene/generated/snapshotTypes";
import {
  baseLayout,
  keptInside,
  movableItem,
  movesBetween,
  movesIn,
  NO_OFFSET,
  type Offset,
  plus,
  sameLayout,
  shifted,
} from "./scene/moves";
import { commandPlayback, followedMoment, setPlaybackTargets, usePlayback } from "./scene/playback";
import { runApartFromItsMoment, scenarioRun } from "./scene/run";
import {
  keptDaily,
  type SceneSource,
  searchFor,
  shownBy,
  targetsFrom,
  targetsText,
  withItsAir,
  withOwnDaily,
} from "./scene/source";
import { useLiveCommands } from "./scene/useLiveCommands";
import { useLiveScene } from "./scene/useLiveScene";
import { useMoveSession } from "./scene/useMoveSession";
import { useSceneLoads } from "./scene/useSceneLoads";
import { type SetSource, useSource } from "./scene/useSource";
import { entityOfOrgan, organOf, plantOf, selectedEntity } from "./selection";
import { CameraFrames } from "./sensors/CameraFrames";
import { CameraView } from "./sensors/CameraView";
import { cameraOf, frustumOverlays } from "./sensors/camera";
import { SensorPanel } from "./sensors/SensorPanel";
import { useSensorReadings } from "./sensors/useSensorReadings";
import { useSimulatorTime } from "./simulatorTime";
import { drawn, failed, failureOf, useLoad } from "./useLoad";
import { Viewport } from "./Viewport";
import { sceneSunlight, sunPathOverlays } from "./weather/sunlight";
import { useWeatherLoads } from "./weather/useWeatherLoads";
import { sunOverlays, windOverlays } from "./weather/weather";
import type { Point3 } from "./world";

const MILLISECONDS_PER_SECOND = 1000;
// A clicked probe is placed this high above the ground, until changed: about
// a crop's height.
const DEFAULT_PROBE_HEIGHT_M = 1;
const EMPTY_PROBES: Point3[] = [];
// How near the camera may stand to the pose framed for it, in metres, and
// still be taken as not moved since: the HUD samples it as drawn.
const FRAMED_STILL_M = 0.01;

function samePoint(a: Point3, b: Point3): boolean {
  return a.x === b.x && a.y === b.y && a.z === b.z;
}

function samePose(a: CameraPose, b: CameraPose): boolean {
  return samePoint(a.position, b.position) && samePoint(a.target, b.target);
}

/** The window's width over its height, as it changes. */
function useWindowAspect(): number {
  const [aspect, setAspect] = useState(() => window.innerWidth / window.innerHeight);
  useEffect(() => {
    const resized = () => setAspect(window.innerWidth / window.innerHeight);
    window.addEventListener("resize", resized);
    return () => window.removeEventListener("resize", resized);
  }, []);
  return aspect;
}

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [addressed, setAddressed] = useSource();
  // Opened with nothing chosen, at the bare address, the viewer starts with
  // the choice of what to show open (#201).
  const [chooseFirst] = useState(() => searchFor(addressed) === "");
  // How the panels look (#208): dark unless the person chose light.
  const [panelTheme, setPanelTheme] = usePanelTheme();
  // Whether the viewer shows what the simulator knows and a policy never
  // sees (P09.6): only QA mode asks for truth.
  const [qaMode, setQaMode] = useQaMode();
  // How long the simulator took to answer the latest request, for the HUD.
  const simulatorTime = useSimulatorTime();
  const scenarios = useLoad(SCENARIOS_URL, (_url, fetchFn) => loadScenarios(fetchFn));
  // The scenario shown, as the list describes it: its weathers, its days
  // and its own daily commands.
  const summary =
    addressed.kind === "scenario" && scenarios.status === "loaded"
      ? scenarios.scenarios.find((s) => s.id === addressed.scenarioId)
      : undefined;
  const own = useMemo(() => ownDaily(summary), [summary]);
  // The source drawn: a scenario's with its own daily commands where its
  // address gives none (P09.4). Every change is made to the source drawn,
  // and the address keeps only what differs from the scenario's own.
  const source = useMemo(
    () => (addressed.kind === "scenario" ? withOwnDaily(addressed, own) : addressed),
    [addressed, own],
  );
  const setSource = useCallback(
    (change: SetSource) =>
      setAddressed((current) => {
        const drawn = current.kind === "scenario" ? withOwnDaily(current, own) : current;
        const next = typeof change === "function" ? change(drawn) : change;
        return next.kind === "scenario" ? keptDaily(next, own) : next;
      }),
    [own, setAddressed],
  );
  // Whether a click places a probe, and how high.
  const [placingProbes, setPlacingProbes] = useState(false);
  const [playingClimate, setPlayingClimate] = useState(false);
  const [probeHeight, setProbeHeight] = useState(DEFAULT_PROBE_HEIGHT_M);
  const [presetRequest, setPresetRequest] = useState<PresetRequest | null>(null);
  const [sample, setSample] = useState<ViewSample | null>(null);
  const [pointer, setPointer] = useState<Point3 | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overlayToggles, setOverlayToggles] = useState<OverlayToggles>(ALL_OVERLAYS);
  const [colourBy, setColourBy] = useState<string | null>(null);
  const [showDimensions, setShowDimensions] = useState(false);
  const [byCategory, setByCategory] = useState(false);
  // The plant lab's play, its speed in days a second, and its plants' names.
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<GrowthSpeed>(1);
  const [showPlantNames, setShowPlantNames] = useState(false);
  const liveScenario = source.kind === "live" ? source.scenarioId : null;
  const live = useLiveScene(liveScenario);
  const commands = useLiveCommands(liveScenario);
  // The drag moving the selected item in a Move session (#271), how far
  // from where the session draws it.
  const [dragging, setDragging] = useState<{ entityId: string; by: Offset } | null>(null);

  // What a view starts with once another is shown, chosen or come back to
  // with Back and Forward (#201): nothing selected, unless another layout of
  // the same scenario still holds it; no colouring, no play, and no probe
  // placing unless it has probes.
  function startAfresh(from: SceneSource, to: SceneSource): void {
    // Items moved, or put back (#209), leave the view as it was.
    if (
      to.kind === "scenario" &&
      from.kind === "scenario" &&
      to.scenarioId === from.scenarioId &&
      (baseLayout(to.layout) ?? DEFAULT_LAYOUT) === (baseLayout(from.layout) ?? DEFAULT_LAYOUT)
    ) {
      return;
    }
    if (
      !(to.kind === "scenario" && from.kind === "scenario" && to.scenarioId === from.scenarioId)
    ) {
      setSelectedId(null);
    }
    setPlaying(false);
    setPlayingClimate(false);
    setColourBy(null);
    if (to.kind !== "scenario" || to.probes === undefined) {
      setPlacingProbes(false);
    }
  }
  // Another scene, scenario, layout or the lab, however it came to be shown.
  const [lastShown, setLastShown] = useState(source);
  if (shownBy(source) !== shownBy(lastShown)) {
    setLastShown(source);
    startAfresh(lastShown, source);
  }

  // The scenario's run drawn, every part of which is asked for under its
  // layout, equipment, openings, schedule, moment and weather; and the same
  // run as the climate's, while the climate field is drawn.
  const run = source.kind === "scenario" ? scenarioRun(source) : null;
  const climate = source.kind === "scenario" && source.field === CLIMATE_FIELD ? run : null;
  // The moment drawn, in seconds into the climate run.
  const moment = run?.time ?? 0;
  // A climate run, apart from its moments, whose colours its field keeps.
  const climateRun = climate === null ? null : runApartFromItsMoment(climate);
  const probes = source.kind === "scenario" ? (source.probes ?? EMPTY_PROBES) : EMPTY_PROBES;

  const { equipment, sceneProgress, cropProgress, organCrop } = useSceneLoads(source, summary, run);
  const scene = drawn(sceneProgress);
  const crop = drawn(cropProgress);
  const {
    fieldProgress,
    field,
    compared,
    fieldView,
    loadedField,
    fieldSlice,
    scaleQuantity,
    fieldScale,
    fieldColours,
    setFieldRange,
  } = useFieldDrawing(source, run, climateRun);
  const fieldName = source.kind === "scenario" ? (source.field ?? null) : null;

  // A run followed as it is played back (P10.2, decision 0041): the moment
  // drawn is the playback's clock, in whole minutes, moved on once the moment
  // asked for before has arrived, so that a slow day is never skipped past
  // half drawn; the run's own play stands aside.
  const followed = source.kind === "scenario" && source.follow ? source.scenarioId : null;
  const [playback, setPlayback] = usePlayback(followed);
  const clockMoment = playback.status === "loaded" ? followedMoment(playback.state) : null;
  const askedMoment = source.kind === "scenario" ? (source.time ?? 0) : null;
  const shownMoment = fieldProgress.shown?.field.timeS ?? null;
  const drawingField = fieldName !== null;
  // A moment whose field failed has arrived as far as it will: the view
  // moves on with the clock, and asks for the next, rather than wait on it.
  const fieldFailed = failed(fieldProgress.latest);
  useEffect(() => {
    if (followed === null || clockMoment === null || clockMoment === askedMoment) {
      return;
    }
    if (drawingField && shownMoment !== askedMoment && !fieldFailed) {
      return;
    }
    setPlayingClimate(false);
    setSource((current) =>
      current.kind === "scenario" ? withTime(current, clockMoment) : current,
    );
  }, [followed, clockMoment, askedMoment, shownMoment, drawingField, fieldFailed, setSource]);
  // Followed, the run drawn changes its targets as the run played back does
  // (#274, decision 0043), so that every part of it is asked for with them.
  const playedTargets = playback.status === "loaded" ? targetsText(playback.state.targets) : null;
  useEffect(() => {
    if (followed === null || playedTargets === null) {
      return;
    }
    setSource((current) =>
      current.kind === "scenario" && targetsText(current.targets) !== playedTargets
        ? withTargets(current, targetsFrom(playedTargets) ?? [])
        : current,
    );
  }, [followed, playedTargets, setSource]);
  // What the view changes of the scenario's own run, which is the one
  // played back: any of these makes it another run.
  const playedLayout = playback.status === "loaded" ? playback.state.layout : DEFAULT_LAYOUT;
  const anotherRun =
    addressed.kind === "scenario" && followed !== null ? runChanges(addressed, playedLayout) : [];
  // What of the moment asked for failed to arrive, while something else of
  // it is drawn in its place: the scene and the field each say why when
  // nothing of them is drawn; the crop never says so itself; nor does a
  // thermostat's heater, which the scene then draws off, not as it runs.
  const failures = [
    sceneProgress.shown === null ? null : failureOf("scene", sceneProgress.latest),
    failureOf("crop", cropProgress.latest),
    fieldProgress.shown === null ? null : failureOf("field", fieldProgress.latest),
    failureOf("equipment", equipment),
  ].filter((failure) => failure !== null);
  const momentFailed = [sceneProgress, cropProgress, fieldProgress].some(({ latest }) =>
    failed(latest),
  );
  const { served, runManifest, runState } = useQaLoads(qaMode, run);
  const { weather, weatherDay } = useWeatherLoads(run);
  const { probeCharts, houseAir, glazing, openingFlows } = useClimateLoads(climate, probes);
  const cfd = useCfdBoundaries(source);

  // A click on the view places probes too: placing stops once all are placed.
  function setProbes(next: Point3[]): void {
    if (source.kind !== "scenario") {
      return;
    }
    setSource(withProbes(source, next));
    if (next.length >= MAX_PROBES) {
      setPlacingProbes(false);
    }
  }

  // A selection is kept from one run of the lab to the next: its organ is the
  // same organ, of the plant in the same place.
  function setLabRun(change: Partial<LabRun>): void {
    if (source.kind !== "plants") {
      return;
    }
    setSource({ ...source, ...change });
  }

  // A choice starts afresh, even of what is shown already.
  function chooseSource(chosen: SceneSource): void {
    const next = withItsAir(source, chosen);
    commands.forget();
    setSource(next);
    startAfresh(source, next);
  }

  const shown = source.kind === "live" ? live.scene : scene;
  const shownSnapshot = shown.status === "loaded" ? shown.snapshot : null;
  const grown = crop.status === "loaded" ? crop.snapshot : null;
  // The scene, its crop as it stands at the moment drawn, its glazed
  // surfaces carrying their temperatures and its open doors and vents their
  // flows while a climate run is drawn.
  const snapshot = useMemo(() => {
    if (shownSnapshot === null) {
      return null;
    }
    const cropped = grown === null ? shownSnapshot : withCrop(shownSnapshot, grown);
    const glazed = glazing.status === "loaded" ? withGlazing(cropped, glazing.glazing) : cropped;
    return openingFlows.status === "loaded"
      ? withOpeningFlows(glazed, openingFlows.openings)
      : glazed;
  }, [shownSnapshot, grown, glazing, openingFlows]);
  const flowing = openingFlows.status === "loaded" ? openingFlows.openings : null;
  // Overlays and colours are worked out from the scene, which they only read.
  const selected = selectedEntity(snapshot, selectedId);
  // The plant selected: a plant drawn whole, or any part of one.
  const selectedPlant =
    selected === null ? null : selected.kind === "PLANT" ? selected.entity_id : plantOf(selected);
  const { plantsLight, cropPlant } = usePlantLoads({
    run,
    climate,
    organCrop,
    selectedPlant,
    qaMode,
  });
  const selectedCamera = selected === null ? null : cameraOf(selected);

  // The selected item, if it is equipment or a sensor a scenario's view can
  // move, and whether it is being moved; the house it is kept inside.
  const movable = source.kind === "scenario" && selected !== null ? movableItem(selected) : null;
  const layoutShown = source.kind === "scenario" ? source.layout : undefined;
  // A Move session's moves, held until they are applied, all at once; while
  // the view follows the run played back, it starts over with them.
  const moves = useMoveSession({
    source,
    setSource,
    defaultLayout: DEFAULT_LAYOUT,
    followed,
    onPlayback: setPlayback,
    sceneLoading: sceneProgress.latest.status === "loading",
  });
  const moveSession = moves.session;
  if (dragging !== null && (moveSession === null || moveSession.applying)) {
    setDragging(null);
  }
  const moving =
    movable !== null && selected !== null && moveSession !== null && !moveSession.applying;
  const house = useMemo(
    () => snapshot?.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS") ?? null,
    [snapshot],
  );
  // A run followed without a camera of its own is shown whole, its house
  // framed, rather than from its corner at the world's origin, where the
  // presets look; the address keeps the pose. Framed from the scene the
  // latest request asked for, never one kept on show while another envelope
  // is on its way; framed again as the window changes shape, as when it is
  // moved beside a consumer's, while the camera stands where it was framed,
  // never once a person has moved it.
  const latestScene = sceneProgress.latest;
  const latestBounds = useMemo(() => {
    const bounds =
      latestScene.status === "loaded"
        ? latestScene.snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS")
        : undefined;
    return bounds?.shape.shape === "box"
      ? {
          base: bounds.transform.position,
          size: { x: bounds.shape.size_x, y: bounds.shape.size_y, z: bounds.shape.size_z },
        }
      : null;
  }, [latestScene]);
  const aspect = useWindowAspect();
  const followedCamera = source.kind === "scenario" ? source.camera : undefined;
  // The pose last framed here, to tell it from one a person chose.
  const [framed, setFramed] = useState<CameraPose | null>(null);
  const cameraAt = sample?.camera ?? null;
  useEffect(() => {
    if (followed === null || latestBounds === null) {
      return;
    }
    const untouched =
      followedCamera === undefined ||
      (framed !== null &&
        samePose(followedCamera, framed) &&
        cameraAt !== null &&
        Math.hypot(
          cameraAt.x - framed.position.x,
          cameraAt.y - framed.position.y,
          cameraAt.z - framed.position.z,
        ) < FRAMED_STILL_M);
    if (!untouched) {
      return;
    }
    const pose = framing(latestBounds.base, latestBounds.size, aspect);
    if (followedCamera !== undefined && samePose(followedCamera, pose)) {
      return;
    }
    setFramed(pose);
    setSource((current) =>
      current.kind === "scenario" && current.follow ? { ...current, camera: pose } : current,
    );
  }, [followed, latestBounds, aspect, followedCamera, framed, cameraAt, setSource]);
  // Each item a Move session moves, by entity: where the session draws it,
  // from where the scene shown places it, the scene of the layout the
  // session started from; the selected item's drag under way added.
  const itemEntities = useMemo(() => {
    const entities = new Map<string, SceneEntity>();
    for (const entity of snapshot?.entities ?? []) {
      const item = movableItem(entity);
      if (item !== null) {
        entities.set(item, entity);
      }
    }
    return entities;
  }, [snapshot]);
  const sessionMoves = moveSession === null ? {} : movesBetween(moveSession.from, moveSession.to);
  const nudged: Record<string, Offset> = {};
  for (const [item, by] of Object.entries(sessionMoves)) {
    const entity = itemEntities.get(item);
    if (entity !== undefined) {
      nudged[entity.entity_id] = by;
    }
  }
  const placedBy = movable === null ? null : (sessionMoves[movable] ?? null);
  if (dragging !== null && selected !== null && dragging.entityId === selected.entity_id) {
    nudged[dragging.entityId] = plus(placedBy ?? NO_OFFSET, dragging.by);
  }
  const selectedNudge = selected === null ? undefined : nudged[selected.entity_id];
  const drawnSelected =
    selected === null || selectedNudge === undefined ? selected : shifted(selected, selectedNudge);
  // How far the selected item stands from where its layout places it, as the
  // session draws it, a drag under way included.
  const layoutMoves = movesIn(moveSession === null ? layoutShown : moveSession.to);
  const standsBy = (() => {
    if (movable === null) {
      return null;
    }
    const placed = layoutMoves[movable] ?? null;
    const by = dragging !== null && dragging.entityId === selected?.entity_id ? dragging.by : null;
    const total = by === null ? placed : plus(placed ?? NO_OFFSET, by);
    return total === null || (total.dx === 0 && total.dy === 0) ? null : total;
  })();

  // A session's moves as the Move panel lists them, by what each item is
  // called, and what applying them does.
  const moveDraft: MoveDraft | null =
    moveSession === null
      ? null
      : {
          moves: Object.entries(movesIn(moveSession.to))
            .filter(([, by]) => by.dx !== 0 || by.dy !== 0)
            .map(([item, by]) => ({ item, label: itemEntities.get(item)?.label ?? item, by })),
          changed: moves.changed,
          following: followed !== null,
          applying: moveSession.applying,
          failure: moveSession.failure,
        };
  function dropMove(by: Offset | null): void {
    setDragging(null);
    if (movable !== null && by !== null && (by.dx !== 0 || by.dy !== 0)) {
      moves.move(movable, by);
    }
  }

  // Escape cancels a Move session's moves, unless it cancels a drag
  // (`MoveDrag`).
  const drafting = moveSession !== null && !moveSession.applying;
  const cancelMoves = moves.cancel;
  useEffect(() => {
    if (!drafting) {
      return;
    }
    function cancel(event: KeyboardEvent): void {
      if (event.key === "Escape" && !event.defaultPrevented) {
        cancelMoves();
      }
    }
    window.addEventListener("keydown", cancel);
    return () => window.removeEventListener("keydown", cancel);
  }, [drafting, cancelMoves]);

  // The Move panel: for the selected item, if it can be moved, and for a
  // session under way, whatever is selected.
  const movePanel =
    source.kind === "scenario" && (movable !== null || moveDraft !== null) ? (
      <MovePanel
        item={
          movable === null || selected === null
            ? null
            : { label: selected.label ?? movable, movedBy: standsBy }
        }
        draft={moveDraft}
        onMove={() => {
          setPlacingProbes(false);
          moves.start();
        }}
        onPutBack={moves.putBack}
        onPutEverythingBack={moves.putEverythingBack}
        onApply={() => void moves.apply()}
        onCancel={moves.cancel}
      />
    ) : null;

  // The run's observation log while a sensor or a camera is selected.
  const sensors = useSensorReadings(selected, run, qaMode);

  // Every plant's name, in the plant lab if asked for, and in a scenario's
  // view in QA mode, with its day's light in a climate run's.
  const showingNames =
    (source.kind === "plants" && showPlantNames) || (source.kind === "scenario" && qaMode);
  const lightOn = qaMode && plantsLight.status === "loaded" ? plantsLight.light : null;
  const probedField = field.status === "loaded" ? field.field : null;
  const outside = weather.status === "loaded" ? weather.weather : null;
  // A climate run's view is lit by the sun, and shows its path through the
  // day; every other view keeps the fixed light, so that it draws as before.
  const sunlit = source.kind === "scenario" && source.field === CLIMATE_FIELD;
  const sunlight = useMemo(
    () =>
      !sunlit || snapshot === null || outside === null ? null : sceneSunlight(snapshot, outside),
    [sunlit, snapshot, outside],
  );
  const sunsDay = sunlit && weatherDay.status === "loaded" ? weatherDay.day : null;
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
        return { ...current, day: labDay + 1 };
      });
    }, MILLISECONDS_PER_SECOND / speed);
    return () => window.clearTimeout(next);
  }, [playing, labDay, shownDay, speed, setSource]);
  const colourProperties = useMemo(
    () => (snapshot === null ? [] : scalarProperties(snapshot)),
    [snapshot],
  );
  const colouring = useMemo(
    () => (snapshot === null || colourBy === null ? null : colouringBy(snapshot, colourBy)),
    [snapshot, colourBy],
  );
  // The sun's two halves load on their own: the sun now, above the horizon
  // only, and its day's path; the card says which of them is drawn.
  const sunNow = useMemo(
    () => (snapshot === null || outside === null ? [] : sunOverlays(snapshot, outside)),
    [snapshot, outside],
  );
  const sunPath = useMemo(
    () => (snapshot === null || sunsDay === null ? [] : sunPathOverlays(snapshot, sunsDay)),
    [snapshot, sunsDay],
  );
  // What each overlay over the scene draws, shown or hidden: hiding one
  // leaves out its primitives, never what they are drawn from.
  const scenePrimitives = useMemo(
    () => ({
      openingFlows:
        snapshot === null || flowing === null ? [] : openingFlowOverlays(snapshot, flowing),
      wind: snapshot === null || outside === null ? [] : windOverlays(snapshot, outside),
      sun: [...sunNow, ...sunPath],
      cameraViews: snapshot === null ? [] : frustumOverlays(snapshot),
      probes:
        probedField === null
          ? []
          : probeOverlays(probes, probedField, qaMode ? scaleQuantity : null),
    }),
    [snapshot, flowing, outside, sunNow, sunPath, probes, probedField, qaMode, scaleQuantity],
  );
  const overlays = useMemo(
    () => [
      ...(drawnSelected === null ? [] : selectionOverlays(drawnSelected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames
        ? plantNameOverlays(snapshot, (plantId) =>
            lightOn === null ? null : (describePlantLight(lightOn, plantId)?.day ?? null),
          )
        : []),
      ...shownPrimitives(scenePrimitives, overlayToggles),
    ],
    [
      drawnSelected,
      overlayToggles,
      snapshot,
      showDimensions,
      showingNames,
      lightOn,
      scenePrimitives,
    ],
  );

  const fieldLayer =
    loadedField === null || fieldColours === null ? null : fieldView === "streamlines" ? (
      <FieldStreamlines field={loadedField} range={fieldColours} />
    ) : fieldSlice !== null ? (
      <FieldSlice field={loadedField} slice={fieldSlice} range={fieldColours} />
    ) : (
      <FieldArrows field={loadedField} range={fieldColours} />
    );
  // The overlays over the scene that have something to draw, which the
  // display options switch and "What am I seeing?" explains (#205).
  const overlaysDrawn = sceneOverlaysDrawn(scenePrimitives, fieldLayer !== null);
  // The kinds the scene holds, and how long its world axes are, for what the
  // card says the scene draws; the empty view draws its own axes.
  const kindsShown = useMemo(
    () => (snapshot === null ? null : new Set(snapshot.entities.map((entity) => entity.kind))),
    [snapshot],
  );
  const axesLengthM = useMemo(() => worldAxesLength(snapshot), [snapshot]);

  const liveStatus: LiveStatus | null =
    source.kind === "live"
      ? { connection: live.connection, frame: live.frame, problem: commands.problem }
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
        sunlight={sunlight}
        initialPose={
          source.kind === "plants"
            ? PLANT_LAB_POSE
            : source.kind === "scenario"
              ? (source.camera ?? null)
              : null
        }
        onSample={setSample}
        onPointer={setPointer}
        onSelect={setSelectedId}
        onProbe={
          placingProbes && probedField !== null
            ? (ground) => setProbes([...probes, { ...ground, z: probeHeight }])
            : null
        }
        moving={
          moving && selected !== null
            ? {
                heightM: selected.transform.position.z,
                // From where the session draws the item.
                shape: (by) =>
                  keptInside(by, placedBy === null ? selected : shifted(selected, placedBy), house),
                onDrag: (by) =>
                  setDragging(by === null ? null : { entityId: selected.entity_id, by }),
                onDrop: dropMove,
              }
            : null
        }
        nudged={nudged}
      >
        {overlayToggles.airField && fieldLayer}
        {cfd.status === "loaded" && <CfdBoundaries geometry={cfd.geometry} />}
      </Viewport>
      <div className="viewer-panels">
        <div className="panel-column">
          <InfoPanel
            build={build}
            scenarios={scenarios}
            source={source}
            scene={shown.status === "loaded" && snapshot !== null ? { ...shown, snapshot } : shown}
            failures={source.kind === "live" ? [] : failures}
            chooseFirst={chooseFirst}
            theme={panelTheme}
            onTheme={setPanelTheme}
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
                drawn={overlaysDrawn}
                fieldView={fieldView}
                overlays={overlayToggles}
                onOverlays={setOverlayToggles}
                qaMode={qaMode}
                onQaMode={setQaMode}
              />
            )}
            {qaMode && (
              <QaPanel
                build={build}
                served={served}
                manifest={runManifest}
                state={runState}
                onSelect={
                  snapshot === null
                    ? null
                    : (id) => setSelectedId(`${snapshot.greenhouse_id}_${id}`)
                }
              />
            )}
            {followed !== null && (
              <PlaybackPanel
                load={playback}
                days={summary?.duration_days ?? null}
                changed={anotherRun}
                onCommand={(command) => void commandPlayback(followed, command).then(setPlayback)}
                onStart={() => void commandPlayback(followed, "start").then(setPlayback)}
                onOwnRun={() => setSource((current) => withoutRunChanges(current, playedLayout))}
                onStop={() =>
                  setSource((current) => {
                    if (current.kind !== "scenario") {
                      return current;
                    }
                    const { follow: _, ...rest } = current;
                    return rest;
                  })
                }
              />
            )}
            {source.kind === "scenario" && (
              <ScenarioPanels
                source={source}
                snapshot={snapshot}
                weathers={summary?.weathers ?? []}
                days={summary?.duration_days ?? 1}
                loads={{ field, compared, weather, weatherDay, houseAir, probeCharts, cfd }}
                thermostat={runningThermostat(equipment)}
                setpoints={
                  summary?.thermostat
                    ? equipment.status === "loaded"
                      ? equipment.equipment.thermostat
                      : null
                    : undefined
                }
                onTargets={(targets) => {
                  if (followed !== null) {
                    void setPlaybackTargets(followed, targets).then(setPlayback);
                    return;
                  }
                  setSource((current) =>
                    current.kind === "scenario" ? withTargetsSet(current, targets) : current,
                  );
                }}
                momentFailed={momentFailed}
                fieldView={fieldView}
                fieldSlice={fieldSlice}
                probes={probes}
                placing={placingProbes}
                probeHeight={probeHeight}
                playingClimate={playingClimate}
                onSource={setSource}
                onProbes={setProbes}
                onPlacing={setPlacingProbes}
                onProbeHeight={setProbeHeight}
                onPlayingClimate={setPlayingClimate}
                onOwnRange={() => setFieldRange(null)}
              />
            )}
            {source.kind === "plants" && (
              <LabPanels
                run={source}
                shownDay={shownDay}
                selected={selected}
                playing={playing}
                speed={speed}
                showNames={showPlantNames}
                onRun={setLabRun}
                onPlaying={setPlaying}
                onSpeed={setSpeed}
                onShowNames={setShowPlantNames}
                onSelectOrgan={(organId) => setSelectedId(entityOfOrgan(snapshot, organId))}
              />
            )}
          </InfoPanel>
          {selected ? (
            <Inspector
              // Where it is drawn, a Move session's moves included.
              entity={drawnSelected ?? selected}
              overlays={overlayToggles}
              onOverlays={setOverlayToggles}
              onClear={() => setSelectedId(null)}
            >
              {snapshot !== null && selectedCamera !== null && (
                <>
                  <CameraView snapshot={snapshot} spec={selectedCamera} />
                  <CameraFrames cameraId={selectedCamera.cameraId} state={sensors.readings} />
                </>
              )}
              {selectedPlant !== null && <PlantLight plantId={selectedPlant} state={plantsLight} />}
              {selectedPlant !== null && (
                <PlantDays
                  state={cropPlant}
                  selectedOrgan={organOf(selected)}
                  onSelect={(organId) => setSelectedId(entityOfOrgan(snapshot, organId))}
                />
              )}
              {selected.kind === "SENSOR" && (
                <SensorPanel
                  sensorId={String(selected.properties.sensor_id)}
                  unit={String(selected.properties.unit)}
                  state={sensors.readings}
                  allOff={sensors.allOff}
                  until={moment}
                  qa={qaMode}
                  imperfect={sensors.imperfect}
                  onImperfect={sensors.setImperfect}
                />
              )}
              {movePanel}
            </Inspector>
          ) : (
            // A session's moves stay on show while nothing is selected.
            movePanel !== null && <div className="inspector">{movePanel}</div>
          )}
        </div>
        <div className="panel-column at-the-end">
          <Hud
            sample={sample}
            pointer={pointer}
            live={liveStatus}
            simulator={simulatorTime}
            onPreset={choosePreset}
            onCommand={commands.send}
          />
          <div className="legends">
            <ControlsHelp />
            <WhatAmISeeing
              view={{
                drawn: overlaysDrawn,
                overlays: overlayToggles,
                fieldView,
                fieldScale,
                fieldArrowSpacing: loadedField === null ? 1 : arrowSpacing(loadedField.grid.cells),
                sun: { now: sunNow.length > 0, path: sunPath.length > 0 },
                colourBy: colouring?.property ?? null,
                byCategory: byCategory && snapshot !== null,
                cfdBoundaries: cfd.status === "loaded",
                dimensions: showDimensions && snapshot !== null,
                kinds: kindsShown,
                axesLengthM,
              }}
            />
            {byCategory && snapshot !== null && (
              <CategoryLegend categories={categoriesIn(snapshot)} />
            )}
            {colouring && <ScalarLegend colouring={colouring} />}
            {cfd.status === "loaded" && <CfdLegend geometry={cfd.geometry} />}
            {fieldScale !== null && overlayToggles.airField && (
              <FieldLegend
                title={fieldScale.title}
                unit={fieldScale.unit}
                range={fieldColours ?? fieldScale.range}
                own={fieldScale.range}
                onRange={setFieldRange}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

type ScenarioOf<S> = Extract<S, { kind: "scenario" }>;

/** What a view's address changes of the run played back, its scenario's own
 * with `played` for its layout (#271), in words: each makes the run drawn
 * another than the one played back. */
function runChanges(source: ScenarioOf<SceneSource>, played: string): string[] {
  const changes: [boolean, string][] = [
    [!sameLayout(source.layout, played, DEFAULT_LAYOUT), "its layout"],
    [source.weather !== undefined, "its weather"],
    [source.clouds !== undefined, "its clouds"],
    [source.wind !== undefined, "its wind"],
    [(source.schedule?.length ?? 0) > 0, "its commands"],
    [source.daily !== undefined, "its daily commands"],
    [source.levels !== undefined, "its equipment"],
    [source.openings !== undefined, "its openings"],
    [source.envelope !== undefined, "its dimensions"],
  ];
  return changes.filter(([changed]) => changed).map(([, said]) => said);
}

/** A view of the run played back, its scenario's own with `played` for its
 * layout: without what would make it another. */
function withoutRunChanges(source: SceneSource, played: string): SceneSource {
  if (source.kind !== "scenario") {
    return source;
  }
  const {
    layout: _layout,
    weather: _weather,
    clouds: _clouds,
    wind: _wind,
    schedule: _schedule,
    daily: _daily,
    levels: _levels,
    openings: _openings,
    envelope: _envelope,
    ...own
  } = source;
  return sameLayout(played, undefined, DEFAULT_LAYOUT) ? own : { ...own, layout: played };
}
