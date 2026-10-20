import { useCallback, useEffect, useMemo, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { CfdBoundaries } from "./cfd/CfdBoundaries";
import { CfdLegend } from "./cfd/CfdLegend";
import { cfdGeometryUrl, loadCfdGeometry } from "./cfd/geometry";
import { daysEnded } from "./clock";
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
import type { ScalarRange } from "./debug/scalar";
import { colouringBy, scalarProperties } from "./debug/scalar";
import { arrowSpacing } from "./fields/arrows";
import type { FieldView } from "./fields/display";
import { defaultSlice, type HeldRanges, heldThrough, quantityScale } from "./fields/drawing";
import { FieldArrows } from "./fields/FieldArrows";
import { FieldLegend } from "./fields/FieldLegend";
import { FieldSlice } from "./fields/FieldSlice";
import { FieldStreamlines } from "./fields/FieldStreamlines";
import { glazingUrl, loadGlazing, withGlazing } from "./fields/glazing";
import { houseAirUrl, loadHouseAir } from "./fields/HouseAir";
import {
  loadOpenings,
  openingFlowOverlays,
  openingsUrl,
  withOpeningFlows,
} from "./fields/openingFlows";
import { loadProbeCharts, probeChartsUrl } from "./fields/ProbeCharts";
import { MAX_PROBES, probeOverlays } from "./fields/probes";
import { CLIMATE_FIELD, fetchField, fieldUrl } from "./fields/source";
import { Hud, type LiveStatus } from "./Hud";
import { InfoPanel } from "./InfoPanel";
import { Inspector } from "./Inspector";
import { PlaybackPanel } from "./PlaybackPanel";
import { cropPlantUrl, cropUrl, loadCropPlant, ORGAN_CROP, withCrop } from "./plants/crop";
import type { GrowthSpeed } from "./plants/LabControls";
import { LabPanels } from "./plants/LabPanels";
import { type LabRun, PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "./plants/lab";
import { describePlantLight, loadPlantsLight, plantsLightUrl } from "./plants/light";
import { plantNameOverlays } from "./plants/names";
import { PlantDays } from "./plants/PlantDays";
import { PlantLight } from "./plants/PlantLight";
import { loadRunManifest, loadServedVersion, runManifestUrl, VERSION_URL } from "./qaMode/manifest";
import { useQaMode } from "./qaMode/mode";
import { QaPanel } from "./qaMode/QaPanel";
import { loadRunState, runStateUrl } from "./qaMode/state";
import type { ViewSample } from "./readouts";
import { ScenarioPanels } from "./ScenarioPanels";
import { WhatAmISeeing, worldAxesLength } from "./SeenInTheView";
import { loadScenarios, ownDaily, SCENARIOS_URL } from "./scenarios";
import { withProbes, withTime } from "./scene/edits";
import { commandPlayback, followedMoment, usePlayback } from "./scene/playback";
import { runApartFromItsMoment, runsSomething, scenarioRun } from "./scene/run";
import {
  changesQuery,
  fetchScene,
  keptDaily,
  loadScene,
  type SceneSource,
  sceneRequest,
  searchFor,
  shownBy,
  withItsAir,
  withOwnDaily,
} from "./scene/source";
import { useLiveCommands } from "./scene/useLiveCommands";
import { useLiveScene } from "./scene/useLiveScene";
import { type SetSource, useSource } from "./scene/useSource";
import { entityOfOrgan, organOf, plantOf, selectedEntity } from "./selection";
import { CameraFrames } from "./sensors/CameraFrames";
import { CameraView } from "./sensors/CameraView";
import { cameraOf, frustumOverlays } from "./sensors/camera";
import { loadSensorReadings, sensorsKey } from "./sensors/readings";
import { SensorPanel } from "./sensors/SensorPanel";
import { useSimulatorTime } from "./simulatorTime";
import { type Pending, type Progress, useLoad, useLoadProgress } from "./useLoad";
import { Viewport } from "./Viewport";
import { sceneSunlight, sunPathOverlays } from "./weather/sunlight";
import {
  loadWeather,
  loadWeatherDay,
  sunOverlays,
  weatherDayUrl,
  weatherUrl,
  windOverlays,
} from "./weather/weather";
import type { Point3 } from "./world";

const MILLISECONDS_PER_SECOND = 1000;
// A clicked probe is placed this high above the ground, until changed: about
// a crop's height.
const DEFAULT_PROBE_HEIGHT_M = 1;
const EMPTY_PROBES: Point3[] = [];
const NO_OPENINGS: readonly string[] = [];

/** What a part of the view draws: the latest of it that loaded, kept while
 * the next is on its way and when the next fails, or else how its latest
 * request stands. */
function drawn<T extends { status: string }>({ shown, latest }: Progress<T>): T | Pending {
  return shown ?? latest;
}

/** Whether a part's latest request failed. */
function failed(latest: { status: string }): boolean {
  return latest.status === "unavailable" || latest.status === "rejected";
}

/** Why a part's latest request failed, in words, if it did. */
function failureOf(part: string, latest: { status: string }): string | null {
  if (latest.status === "unavailable" && "reason" in latest) {
    return `the ${part} is not available (${String(latest.reason)})`;
  }
  if (latest.status === "rejected" && "problems" in latest && Array.isArray(latest.problems)) {
    return `the ${part} was refused (${latest.problems.join("; ")})`;
  }
  return null;
}

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [addressed, setAddressed] = useSource();
  // Opened with nothing chosen, at the bare address, the viewer starts with
  // the choice of what to show open (#201).
  const [chooseFirst] = useState(() => searchFor(addressed) === "");
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
  // Whether sensors' readings are shown as they err, or, in QA mode, as clean
  // ones'.
  const [sensorsImperfect, setSensorsImperfect] = useState(true);
  const [probeHeight, setProbeHeight] = useState(DEFAULT_PROBE_HEIGHT_M);
  // A range the viewer chose for the field's colours, in place of its own.
  const [fieldRange, setFieldRange] = useState<ScalarRange | null>(null);
  // The colour ranges a climate run's moments have reached, so far.
  const [heldRanges, setHeldRanges] = useState<HeldRanges | null>(null);
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

  // What a view starts with once another is shown, chosen or come back to
  // with Back and Forward (#201): nothing selected, unless another layout of
  // the same scenario still holds it; no colouring, no play, and no probe
  // placing unless it has probes.
  function startAfresh(from: SceneSource, to: SceneSource): void {
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

  // A scenario reopened by its sliders, or the plant lab on another day,
  // keeps its scene on show until the next arrives; any other change of
  // scene starts from loading.
  const openingIds = summary?.openings ?? NO_OPENINGS;
  const sceneAsked = sceneRequest(source, openingIds);
  const sceneProgress = useLoadProgress(
    sceneAsked,
    (_url, fetchFn) => loadScene(source, fetchFn, openingIds),
    {
      group:
        source.kind === "scenario"
          ? `scenario ${source.scenarioId}`
          : source.kind === "plants"
            ? "plants"
            : (sceneAsked ?? ""),
    },
  );
  const scene = drawn(sceneProgress);

  // The scenario's run drawn, every part of which is asked for under its
  // layout, equipment, openings, schedule, moment and weather; and the same
  // run as the climate's, while the climate field is drawn.
  const run = source.kind === "scenario" ? scenarioRun(source) : null;
  const climate = source.kind === "scenario" && source.field === CLIMATE_FIELD ? run : null;
  // The moment drawn, in seconds into the climate run.
  const moment = run?.time ?? 0;
  // A climate run, apart from its moments: its colours keep the widest range
  // its moments have reached, so that a slice keeps its colours as the run
  // plays and goes back. Another run starts afresh.
  const climateRun = climate === null ? null : runApartFromItsMoment(climate);
  const probes = source.kind === "scenario" ? (source.probes ?? EMPTY_PROBES) : EMPTY_PROBES;

  // A crop grown organ by organ, as it stands at the moment drawn, in place
  // of its transplants once a day has ended; the last stays on show until
  // the next day's arrives, and when the next day's fails.
  const organCrop = summary?.crop_model === ORGAN_CROP;
  const cropProgress = useLoadProgress(
    run === null || !organCrop || daysEnded(moment) === 0 ? null : cropUrl(run),
    fetchScene,
    { group: run === null ? "" : `crop ${run.scenarioId}` },
  );
  const crop = drawn(cropProgress);

  // The scenario's field, drawn over its scene, and another compared with it
  // at the probes; the last of each stays on show until the next arrives,
  // and the field's when the next fails.
  const fieldName = source.kind === "scenario" ? (source.field ?? null) : null;
  const fieldProgress = useLoadProgress(
    run === null || fieldName === null ? null : fieldUrl(run.scenarioId, fieldName, run),
    fetchField,
    {
      onAnswer: (state) => {
        if (climateRun !== null && state.status === "loaded") {
          setHeldRanges((held) => heldThrough(held, climateRun, state.field));
        }
      },
    },
  );
  const field = drawn(fieldProgress);

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
  // What the view changes of the scenario's own run, which is the one
  // played back: any of these makes it another run.
  const anotherRun =
    addressed.kind === "scenario" && followed !== null ? runChanges(addressed) : [];
  // What of the moment asked for failed to arrive, while something else of
  // it is drawn in its place: the scene and the field each say why when
  // nothing of them is drawn; the crop never says so itself.
  const failures = [
    sceneProgress.shown === null ? null : failureOf("scene", sceneProgress.latest),
    failureOf("crop", cropProgress.latest),
    fieldProgress.shown === null ? null : failureOf("field", fieldProgress.latest),
  ].filter((failure) => failure !== null);
  const momentFailed = [sceneProgress, cropProgress, fieldProgress].some(({ latest }) =>
    failed(latest),
  );
  const compareName = source.kind === "scenario" ? (source.compare ?? null) : null;
  const compared = useLoad(
    run === null || compareName === null ? null : fieldUrl(run.scenarioId, compareName, run),
    fetchField,
  );

  // In QA mode, the simulator's version and commit, as it says itself, and
  // what the scenario's run drawn is made from.
  const served = useLoad(qaMode ? VERSION_URL : null, loadServedVersion);
  const runManifest = useLoad(
    !qaMode || run === null ? null : runManifestUrl(run.scenarioId, run),
    loadRunManifest,
  );
  // In QA mode, what each process of the run drawn holds at its moment; the
  // last stays on show until the next arrives.
  const runState = useLoad(
    !qaMode || run === null ? null : runStateUrl(run.scenarioId, run),
    loadRunState,
    { group: run === null ? "" : `state ${run.scenarioId}` },
  );

  // The weather outside a scenario at the moment drawn, and through its
  // day, for its chart.
  const weather = useLoad(
    run === null ? null : weatherUrl(run.scenarioId, moment, run.weather),
    loadWeather,
  );
  const weatherDay = useLoad(
    run === null ? null : weatherDayUrl(run.scenarioId, moment, run.weather),
    loadWeatherDay,
  );

  // What the probes read through the climate run drawn, and through the
  // same run all off, up to the moment drawn.
  const probeCharts = useLoad(
    climate === null || probes.length === 0
      ? null
      : probeChartsUrl(climate.scenarioId, { ...climate, probes }),
    loadProbeCharts,
  );
  // The house's air as one volume through the climate run drawn, and the
  // same run all off, up to the moment drawn.
  const houseAir = useLoad(
    climate === null ? null : houseAirUrl(climate.scenarioId, climate),
    loadHouseAir,
  );
  // The glazing at the moment drawn, each wall's and roof slope's
  // temperature, for "Colour by".
  const glazing = useLoad(
    climate === null ? null : glazingUrl(climate.scenarioId, climate),
    loadGlazing,
  );
  // What the open doors and vents pass at the moment drawn, for "Colour by"
  // and their arrows.
  const openingFlows = useLoad(
    climate === null ? null : openingsUrl(climate.scenarioId, climate),
    loadOpenings,
  );

  // The boundaries a CFD solver is given, changed as the scene is, drawn
  // over it when asked for; the last stays on show until the next arrives.
  // How hard its equipment runs does not change them.
  const cfdUrl =
    source.kind === "scenario" && source.cfdBoundaries
      ? cfdGeometryUrl(source.scenarioId, changesQuery({ ...source, levels: {} }, "?"))
      : null;
  const cfd = useLoad(cfdUrl, loadCfdGeometry);

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
  // The light on the plants at the moment drawn, while a plant is selected
  // in a climate run's view, or in QA mode, which labels every plant with
  // it; the last stays on show until the next arrives.
  const plantsLight = useLoad(
    climate === null || (selectedPlant === null && !qaMode)
      ? null
      : plantsLightUrl(climate.scenarioId, climate),
    loadPlantsLight,
  );
  // The plant selected in a crop grown organ by organ, as it stands at the
  // moment drawn, with each day it lived.
  const cropPlant = useLoad(
    run === null || !organCrop || selectedPlant === null ? null : cropPlantUrl(run, selectedPlant),
    loadCropPlant,
  );
  const selectedCamera = selected === null ? null : cameraOf(selected);

  // The run's observation log up to the moment drawn, while a sensor or a
  // camera is selected, and, in QA mode only, what its sensors truly
  // sampled; as clean sensors would have made it, if QA mode asks.
  const sensorSelected = selected?.kind === "SENSOR" || selected?.kind === "CAMERA";
  const sensorRun = sensorSelected ? run : null;
  const clean = qaMode && !sensorsImperfect;
  const sensorReadings = useLoad(
    sensorRun === null
      ? null
      : { scenarioId: sensorRun.scenarioId, run: { ...sensorRun, clean }, truth: qaMode },
    loadSensorReadings,
    { key: sensorsKey },
  );

  // What the sensors read through the same run all off, when something runs.
  const offReadings = useLoad(
    sensorRun === null || !runsSomething(sensorRun)
      ? null
      : {
          scenarioId: sensorRun.scenarioId,
          run: {
            ...sensorRun,
            levels: undefined,
            schedule: undefined,
            daily: [],
            clean,
          },
          truth: false,
        },
    loadSensorReadings,
    { key: sensorsKey },
  );

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
  // How the field is drawn, and the scale its colours run over: air speed for
  // arrows and streamlines, the slice's quantity for a slice.
  const fieldView: FieldView =
    source.kind === "scenario" ? (source.fieldView ?? "arrows") : "arrows";
  const loadedField = field.status === "loaded" ? field.field : null;
  // Worked out once for each field and choice, not on every render: the
  // layers redraw, and trace streamlines afresh, whenever these change.
  const askedSlice = source.kind === "scenario" ? source.slice : undefined;
  const fieldSlice = useMemo(
    () =>
      fieldView === "slice" && loadedField !== null
        ? (askedSlice ?? defaultSlice(loadedField))
        : null,
    [fieldView, loadedField, askedSlice],
  );
  const scaleQuantity = fieldSlice === null ? "speed" : fieldSlice.quantity;
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
      ...(selected === null ? [] : selectionOverlays(selected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames
        ? plantNameOverlays(snapshot, (plantId) =>
            lightOn === null ? null : (describePlantLight(lightOn, plantId)?.day ?? null),
          )
        : []),
      ...shownPrimitives(scenePrimitives, overlayToggles),
    ],
    [selected, overlayToggles, snapshot, showDimensions, showingNames, lightOn, scenePrimitives],
  );

  const fieldScale = useMemo(
    () => (loadedField === null ? null : quantityScale(loadedField, scaleQuantity)),
    [loadedField, scaleQuantity],
  );
  const heldRange =
    heldRanges !== null && heldRanges.run === climateRun
      ? heldRanges.ranges[scaleQuantity]
      : undefined;
  const fieldColours = fieldScale === null ? null : (fieldRange ?? heldRange ?? fieldScale.range);
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
                changed={anotherRun}
                onCommand={(command) => void commandPlayback(followed, command).then(setPlayback)}
                onStart={() => void commandPlayback(followed, "start").then(setPlayback)}
                onOwnRun={() => setSource((current) => withoutRunChanges(current))}
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
          {selected && (
            <Inspector
              entity={selected}
              overlays={overlayToggles}
              onOverlays={setOverlayToggles}
              onClear={() => setSelectedId(null)}
            >
              {snapshot !== null && selectedCamera !== null && (
                <>
                  <CameraView snapshot={snapshot} spec={selectedCamera} />
                  <CameraFrames cameraId={selectedCamera.cameraId} state={sensorReadings} />
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
                  state={sensorReadings}
                  allOff={offReadings}
                  until={moment}
                  qa={qaMode}
                  imperfect={sensorsImperfect}
                  onImperfect={setSensorsImperfect}
                />
              )}
            </Inspector>
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

/** What a view's address changes of its scenario's own run, in words: each
 * makes the run drawn another than the one played back. */
function runChanges(source: ScenarioOf<SceneSource>): string[] {
  const changes: [boolean, string][] = [
    [source.layout !== undefined, "its layout"],
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

/** A view of its scenario's own run, as it is played back: without what
 * would make it another. */
function withoutRunChanges(source: SceneSource): SceneSource {
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
  return own;
}
