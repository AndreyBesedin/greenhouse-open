import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { CfdBoundaries } from "./cfd/CfdBoundaries";
import { CfdControls } from "./cfd/CfdControls";
import { CfdLegend } from "./cfd/CfdLegend";
import { type CfdGeometryState, cfdGeometryUrl, loadCfdGeometry } from "./cfd/geometry";
import { DisplayOptions } from "./DisplayOptions";
import { CategoryLegend } from "./debug/CategoryLegend";
import { categoriesIn } from "./debug/categories";
import { sceneDimensionOverlays } from "./debug/dimensions";
import { ALL_OVERLAYS, type OverlayToggles, selectionOverlays } from "./debug/overlays";
import { ScalarLegend } from "./debug/ScalarLegend";
import type { ScalarRange } from "./debug/scalar";
import { colouringBy, scalarProperties } from "./debug/scalar";
import { EquipmentControls } from "./EquipmentControls";
import { ClimateSchedule } from "./fields/ClimateSchedule";
import { ClimateTime } from "./fields/ClimateTime";
import type { FieldView, Slice } from "./fields/display";
import { defaultSlice, type HeldRanges, heldThrough, quantityScale } from "./fields/drawing";
import { FieldArrows } from "./fields/FieldArrows";
import { FieldControls } from "./fields/FieldControls";
import { FieldLegend } from "./fields/FieldLegend";
import { FieldProbes } from "./fields/FieldProbes";
import { FieldSlice } from "./fields/FieldSlice";
import { FieldStreamlines } from "./fields/FieldStreamlines";
import { type GlazingState, glazingUrl, loadGlazing, withGlazing } from "./fields/glazing";
import { HouseAir, type HouseAirState, houseAirUrl, loadHouseAir } from "./fields/HouseAir";
import {
  loadOpenings,
  type OpeningsState,
  openingFlowOverlays,
  openingsUrl,
  withOpeningFlows,
} from "./fields/openingFlows";
import {
  loadProbeCharts,
  ProbeCharts,
  type ProbeChartsState,
  probeChartsUrl,
} from "./fields/ProbeCharts";
import { MAX_PROBES, probeOverlays } from "./fields/probes";
import { CLIMATE_FIELD, type FieldState, loadField } from "./fields/source";
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
  changesQuery,
  levelsAt,
  loadScene,
  pairsFrom,
  pairsText,
  type SceneSource,
  type SceneState,
  scheduleFrom,
  scheduleText,
  searchFor,
  sourceFromSearch,
  withItsAir,
  withOverride,
} from "./scene/source";
import { useLiveScene } from "./scene/useLiveScene";
import { entityOfOrgan, organOf, plantOf, selectedEntity } from "./selection";
import { CameraFrames } from "./sensors/CameraFrames";
import { CameraView } from "./sensors/CameraView";
import { cameraOf, frustumOverlays } from "./sensors/camera";
import { loadSensorReadings, type SensorReadingsState } from "./sensors/readings";
import { SensorPanel } from "./sensors/SensorPanel";
import { Viewport } from "./Viewport";
import { WeatherPanel } from "./weather/WeatherPanel";
import {
  loadWeather,
  loadWeatherDay,
  sunOverlays,
  type WeatherDayState,
  type WeatherStateOfLoad,
  windOverlays,
} from "./weather/weather";
import type { Point3 } from "./world";

const MILLISECONDS_PER_SECOND = 1000;
// A clicked probe is placed this high above the ground, until changed: about
// a crop's height.
const DEFAULT_PROBE_HEIGHT_M = 1;
const EMPTY_PROBES: Point3[] = [];

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const [scene, setScene] = useState<SceneState>({ status: "none" });
  const [field, setField] = useState<FieldState>({ status: "none" });
  const [cfd, setCfd] = useState<CfdGeometryState>({ status: "none" });
  // Another field, compared with the drawn one at the probes; and whether a
  // click places a probe, and how high.
  const [compared, setCompared] = useState<FieldState>({ status: "none" });
  const [placingProbes, setPlacingProbes] = useState(false);
  const [playingClimate, setPlayingClimate] = useState(false);
  const [probeCharts, setProbeCharts] = useState<ProbeChartsState>({ status: "none" });
  const [houseAir, setHouseAir] = useState<HouseAirState>({ status: "none" });
  const [glazing, setGlazing] = useState<GlazingState>({ status: "none" });
  const [openingFlows, setOpeningFlows] = useState<OpeningsState>({ status: "none" });
  const [sensorReadings, setSensorReadings] = useState<SensorReadingsState>({ status: "none" });
  // The same sensor through the same run with everything off, to compare.
  const [offReadings, setOffReadings] = useState<SensorReadingsState>({ status: "none" });
  const [weather, setWeather] = useState<WeatherStateOfLoad>({ status: "none" });
  const [weatherDay, setWeatherDay] = useState<WeatherDayState>({ status: "none" });
  // Whether sensors' readings are shown as they err, or as clean ones', for QA.
  const [sensorsImperfect, setSensorsImperfect] = useState(true);
  const [probeHeight, setProbeHeight] = useState(DEFAULT_PROBE_HEIGHT_M);
  // A range the viewer chose for the field's colours, in place of its own.
  const [fieldRange, setFieldRange] = useState<ScalarRange | null>(null);
  // The colour ranges a climate run's moments have reached, so far.
  const [heldRanges, setHeldRanges] = useState<HeldRanges | null>(null);
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
  // A scenario's CFD solution depends on its layout, and its climate on how
  // hard its equipment runs and how far its doors and vents stand open: kept
  // as the address writes them, so that the field is loaded again only when
  // they change.
  const fieldLayout = source.kind === "scenario" ? source.layout : undefined;
  const fieldLevels = source.kind === "scenario" ? pairsText(source.levels) : "";
  const fieldOpenings = source.kind === "scenario" ? pairsText(source.openings) : "";
  const fieldSchedule = source.kind === "scenario" ? scheduleText(source.schedule) : "";
  const fieldTime = source.kind === "scenario" ? (source.time ?? 0) : 0;
  const fieldWeather = source.kind === "scenario" ? source.weather : undefined;
  // A climate run, apart from its moments: its colours keep the widest range
  // its moments have reached, so that a slice keeps its colours as the run
  // plays and goes back. Another run starts afresh.
  const climateRun =
    fieldScenario !== null && fieldName === CLIMATE_FIELD
      ? [
          fieldScenario,
          fieldLayout ?? "",
          fieldWeather ?? "",
          fieldLevels,
          fieldOpenings,
          fieldSchedule,
        ].join("|")
      : null;
  useEffect(() => {
    if (fieldScenario === null || fieldName === null) {
      setField({ status: "none" });
      return;
    }
    const run = climateRun;
    let current = true;
    setField((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    const changes = {
      layout: fieldLayout,
      levels: pairsFrom(fieldLevels) ?? {},
      openings: pairsFrom(fieldOpenings) ?? {},
      schedule: scheduleFrom(fieldSchedule) ?? [],
      time: fieldTime,
      weather: fieldWeather,
    };
    void loadField(fieldScenario, fieldName, changes).then((state) => {
      if (current) {
        setField(state);
        if (run !== null && state.status === "loaded") {
          setHeldRanges((held) => heldThrough(held, run, state.field));
        }
      }
    });
    return () => {
      current = false;
    };
  }, [
    fieldScenario,
    fieldName,
    fieldLayout,
    fieldLevels,
    fieldOpenings,
    fieldSchedule,
    fieldTime,
    fieldWeather,
    climateRun,
  ]);

  // The weather outside a scenario at the moment drawn; the last stays on
  // show until the next arrives.
  const weatherScenario = source.kind === "scenario" ? source.scenarioId : null;
  useEffect(() => {
    if (weatherScenario === null) {
      setWeather({ status: "none" });
      return;
    }
    let current = true;
    setWeather((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadWeather(weatherScenario, fieldTime, fieldWeather).then((state) => {
      if (current) {
        setWeather(state);
      }
    });
    return () => {
      current = false;
    };
  }, [weatherScenario, fieldTime, fieldWeather]);

  // The weather through the runs' first day, for its chart.
  useEffect(() => {
    if (weatherScenario === null) {
      setWeatherDay({ status: "none" });
      return;
    }
    let current = true;
    setWeatherDay((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadWeatherDay(weatherScenario, fieldWeather).then((state) => {
      if (current) {
        setWeatherDay(state);
      }
    });
    return () => {
      current = false;
    };
  }, [weatherScenario, fieldWeather]);

  // The field compared with the drawn one, loaded as the drawn one is.
  const compareName = source.kind === "scenario" ? (source.compare ?? null) : null;
  useEffect(() => {
    if (fieldScenario === null || compareName === null) {
      setCompared({ status: "none" });
      return;
    }
    let current = true;
    setCompared((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    const changes = {
      layout: fieldLayout,
      levels: pairsFrom(fieldLevels) ?? {},
      openings: pairsFrom(fieldOpenings) ?? {},
      schedule: scheduleFrom(fieldSchedule) ?? [],
      time: fieldTime,
      weather: fieldWeather,
    };
    void loadField(fieldScenario, compareName, changes).then((state) => {
      if (current) {
        setCompared(state);
      }
    });
    return () => {
      current = false;
    };
  }, [
    fieldScenario,
    compareName,
    fieldLayout,
    fieldLevels,
    fieldOpenings,
    fieldSchedule,
    fieldTime,
    fieldWeather,
  ]);

  // What the probes read through the climate run drawn, and through the
  // same run all off, up to the moment drawn; the last stays on show until
  // the next arrives.
  const chartsUrl =
    source.kind === "scenario" &&
    source.field === CLIMATE_FIELD &&
    source.probes !== undefined &&
    source.probes.length > 0
      ? probeChartsUrl(source.scenarioId, { ...source, probes: source.probes })
      : null;
  useEffect(() => {
    if (chartsUrl === null) {
      setProbeCharts({ status: "none" });
      return;
    }
    let current = true;
    setProbeCharts((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadProbeCharts(chartsUrl).then((state) => {
      if (current) {
        setProbeCharts(state);
      }
    });
    return () => {
      current = false;
    };
  }, [chartsUrl]);

  // The house's air as one volume through the climate run drawn, and the
  // same run all off, up to the moment drawn; the last stays on show until
  // the next arrives.
  const houseUrl =
    source.kind === "scenario" && source.field === CLIMATE_FIELD
      ? houseAirUrl(source.scenarioId, source)
      : null;
  useEffect(() => {
    if (houseUrl === null) {
      setHouseAir({ status: "none" });
      return;
    }
    let current = true;
    setHouseAir((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadHouseAir(houseUrl).then((state) => {
      if (current) {
        setHouseAir(state);
      }
    });
    return () => {
      current = false;
    };
  }, [houseUrl]);

  // The glazing at the moment drawn, each wall's and roof slope's
  // temperature, for "Colour by"; the last stays on show until the next
  // arrives.
  const glassUrl =
    source.kind === "scenario" && source.field === CLIMATE_FIELD
      ? glazingUrl(source.scenarioId, source)
      : null;
  useEffect(() => {
    if (glassUrl === null) {
      setGlazing({ status: "none" });
      return;
    }
    let current = true;
    setGlazing((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadGlazing(glassUrl).then((state) => {
      if (current) {
        setGlazing(state);
      }
    });
    return () => {
      current = false;
    };
  }, [glassUrl]);

  // What the open doors and vents pass at the moment drawn, for "Colour by"
  // and their arrows; the last stays on show until the next arrives.
  const flowsUrl =
    source.kind === "scenario" && source.field === CLIMATE_FIELD
      ? openingsUrl(source.scenarioId, source)
      : null;
  useEffect(() => {
    if (flowsUrl === null) {
      setOpeningFlows({ status: "none" });
      return;
    }
    let current = true;
    setOpeningFlows((previous) =>
      previous.status === "loaded" ? previous : { status: "loading" },
    );
    void loadOpenings(flowsUrl).then((state) => {
      if (current) {
        setOpeningFlows(state);
      }
    });
    return () => {
      current = false;
    };
  }, [flowsUrl]);

  // The boundaries a CFD solver is given, changed as the scene is, drawn
  // over it when asked for; the last stays on show until the next arrives.
  // How hard its equipment runs does not change them.
  const cfdUrl =
    source.kind === "scenario" && source.cfdBoundaries
      ? cfdGeometryUrl(source.scenarioId, changesQuery({ ...source, levels: {} }, "?"))
      : null;
  useEffect(() => {
    if (cfdUrl === null) {
      setCfd({ status: "none" });
      return;
    }
    let current = true;
    setCfd((previous) => (previous.status === "loaded" ? previous : { status: "loading" }));
    void loadCfdGeometry(cfdUrl).then((state) => {
      if (current) {
        setCfd(state);
      }
    });
    return () => {
      current = false;
    };
  }, [cfdUrl]);

  function setScenarioSource(next: SceneSource): void {
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  function chooseField(name: string | null): void {
    if (source.kind !== "scenario") {
      return;
    }
    const { field: _, fieldView: __, slice: ___, compare, probes, ...rest } = source;
    setFieldRange(null);
    if (name === null) {
      setPlacingProbes(false);
      setScenarioSource(rest);
      return;
    }
    // Its probes stay where they are, and so does what it is compared with,
    // unless that is the field now drawn.
    setScenarioSource({
      ...rest,
      field: name,
      ...(probes === undefined ? {} : { probes }),
      ...(compare === undefined || compare === name ? {} : { compare }),
    });
  }

  function setProbes(probes: Point3[]): void {
    if (source.kind === "scenario") {
      const { probes: _, ...rest } = source;
      setScenarioSource(probes.length === 0 ? rest : { ...rest, probes });
      if (probes.length >= MAX_PROBES) {
        setPlacingProbes(false);
      }
    }
  }

  function compareWith(name: string | null): void {
    if (source.kind === "scenario") {
      const { compare: _, ...rest } = source;
      setScenarioSource(name === null ? rest : { ...rest, compare: name });
    }
  }

  function chooseFieldView(view: FieldView): void {
    if (source.kind !== "scenario" || field.status !== "loaded") {
      return;
    }
    const { slice, ...rest } = source;
    setFieldRange(null);
    setScenarioSource(
      view === "slice"
        ? { ...rest, fieldView: view, slice: slice ?? defaultSlice(field.field) }
        : { ...rest, fieldView: view },
    );
  }

  function showCfdBoundaries(show: boolean): void {
    if (source.kind === "scenario") {
      const { cfdBoundaries: _, ...rest } = source;
      setScenarioSource(show ? { ...rest, cfdBoundaries: true } : rest);
    }
  }

  function chooseSlice(slice: Slice): void {
    if (source.kind === "scenario") {
      if (source.slice?.quantity !== slice.quantity) {
        setFieldRange(null);
      }
      setScenarioSource({ ...source, slice });
    }
  }

  // Another weather to run the scenario under, or its own.
  function chooseWeather(chosen: string | undefined): void {
    if (source.kind !== "scenario") {
      return;
    }
    const { weather: _, ...rest } = source;
    setScenarioSource(chosen === undefined ? rest : { ...rest, weather: chosen });
  }

  function setOpenings(openings: Record<string, number>): void {
    if (source.kind !== "scenario") {
      return;
    }
    const next: SceneSource = { ...source, openings };
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
  }

  // A moment of the climate run, kept in the address; 0, its start, is left out.
  const setClimateTime = useCallback((seconds: number): void => {
    setSource((current) => {
      if (current.kind !== "scenario") {
        return current;
      }
      const { time: _, ...rest } = current;
      const next: SceneSource = seconds > 0 ? { ...rest, time: seconds } : rest;
      history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
      return next;
    });
  }, []);

  // Equipment switched while a climate run is drawn past its start is an
  // override at that moment; otherwise it is set from the start.
  function setLevels(levels: Record<string, number>): void {
    if (source.kind !== "scenario") {
      return;
    }
    const now = source.time ?? 0;
    if (source.field === CLIMATE_FIELD && now > 0) {
      const standing = levelsAt(source);
      const changed = Object.fromEntries(
        Object.entries(levels).filter(([actuatorId, level]) => standing[actuatorId] !== level),
      );
      setScenarioSource({ ...source, schedule: withOverride(source.schedule ?? [], now, changed) });
      return;
    }
    setScenarioSource({ ...source, levels });
  }

  function removeCommand(index: number): void {
    if (source.kind !== "scenario") {
      return;
    }
    const { schedule: _, ...rest } = source;
    const schedule = (source.schedule ?? []).filter((__, at) => at !== index);
    setScenarioSource(schedule.length === 0 ? rest : { ...rest, schedule });
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

  function chooseSource(chosen: SceneSource): void {
    const next = withItsAir(source, chosen);
    commandGeneration.current += 1;
    history.replaceState(null, "", `${location.pathname}${searchFor(next)}`);
    setSource(next);
    setCommandProblem(null);
    // Another layout of the same scenario keeps the selection, while what is
    // selected is still there; anything else starts afresh.
    if (
      !(
        chosen.kind === "scenario" &&
        source.kind === "scenario" &&
        chosen.scenarioId === source.scenarioId
      )
    ) {
      setSelectedId(null);
    }
    setPlaying(false);
    setColourBy(null);
    if (next.kind !== "scenario" || next.probes === undefined) {
      setPlacingProbes(false);
    }
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
  const shownSnapshot = shown.status === "loaded" ? shown.snapshot : null;
  // The scene, its glazed surfaces carrying their temperatures and its open
  // doors and vents their flows while a climate run is drawn.
  const snapshot = useMemo(() => {
    if (shownSnapshot === null) {
      return null;
    }
    const glazed =
      glazing.status === "loaded" ? withGlazing(shownSnapshot, glazing.glazing) : shownSnapshot;
    return openingFlows.status === "loaded"
      ? withOpeningFlows(glazed, openingFlows.openings)
      : glazed;
  }, [shownSnapshot, glazing, openingFlows]);
  const flowing = openingFlows.status === "loaded" ? openingFlows.openings : null;
  // Overlays and colours are worked out from the scene, which they only read.
  const selected = selectedEntity(snapshot, selectedId);
  const selectedCamera = selected === null ? null : cameraOf(selected);

  // The run's observation log up to the moment drawn, and what its sensors
  // truly sampled, while a sensor or a camera is selected.
  const sensorSelected = selected?.kind === "SENSOR" || selected?.kind === "CAMERA";
  useEffect(() => {
    if (!sensorSelected || fieldScenario === null) {
      setSensorReadings({ status: "none" });
      return;
    }
    let current = true;
    setSensorReadings((previous) =>
      previous.status === "loaded" ? previous : { status: "loading" },
    );
    void loadSensorReadings(fieldScenario, {
      layout: fieldLayout,
      levels: pairsFrom(fieldLevels) ?? {},
      openings: pairsFrom(fieldOpenings) ?? {},
      schedule: scheduleFrom(fieldSchedule) ?? [],
      time: fieldTime,
      clean: !sensorsImperfect,
      weather: fieldWeather,
    }).then((state) => {
      if (current) {
        setSensorReadings(state);
      }
    });
    return () => {
      current = false;
    };
  }, [
    sensorSelected,
    fieldScenario,
    fieldLayout,
    fieldLevels,
    fieldOpenings,
    fieldSchedule,
    fieldTime,
    fieldWeather,
    sensorsImperfect,
  ]);

  // What the sensors read through the same run all off, when something runs.
  const runsSomething = fieldLevels !== "" || fieldSchedule !== "";
  useEffect(() => {
    if (!sensorSelected || fieldScenario === null || !runsSomething) {
      setOffReadings({ status: "none" });
      return;
    }
    let current = true;
    void loadSensorReadings(fieldScenario, {
      layout: fieldLayout,
      openings: pairsFrom(fieldOpenings) ?? {},
      time: fieldTime,
      clean: !sensorsImperfect,
      weather: fieldWeather,
    }).then((state) => {
      if (current) {
        setOffReadings(state);
      }
    });
    return () => {
      current = false;
    };
  }, [
    sensorSelected,
    runsSomething,
    fieldScenario,
    fieldLayout,
    fieldOpenings,
    fieldTime,
    fieldWeather,
    sensorsImperfect,
  ]);

  const showingNames = source.kind === "plants" && showPlantNames;
  const probes = source.kind === "scenario" ? (source.probes ?? EMPTY_PROBES) : EMPTY_PROBES;
  const probedField = field.status === "loaded" ? field.field : null;
  const outside = weather.status === "loaded" ? weather.weather : null;
  const overlays = useMemo(
    () => [
      ...(selected === null ? [] : selectionOverlays(selected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames ? plantNameOverlays(snapshot) : []),
      ...(probedField === null ? [] : probeOverlays(probes, probedField)),
      ...(snapshot === null ? [] : frustumOverlays(snapshot)),
      ...(snapshot === null || outside === null ? [] : windOverlays(snapshot, outside)),
      ...(snapshot === null || outside === null ? [] : sunOverlays(snapshot, outside)),
      ...(snapshot === null || flowing === null ? [] : openingFlowOverlays(snapshot, flowing)),
    ],
    [
      selected,
      overlayToggles,
      snapshot,
      showDimensions,
      showingNames,
      probes,
      probedField,
      outside,
      flowing,
    ],
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
        {fieldLayer}
        {cfd.status === "loaded" && <CfdBoundaries geometry={cfd.geometry} />}
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
                layout={source.layout}
                chosen={source.field ?? null}
                state={field}
                view={fieldView}
                slice={fieldSlice}
                onChoose={chooseField}
                onView={chooseFieldView}
                onSlice={chooseSlice}
              />
            )}
            {source.kind === "scenario" && source.field === CLIMATE_FIELD && (
              <ClimateTime
                time={fieldTime}
                shown={field.status === "loaded" ? field.field.timeS : null}
                playing={playingClimate}
                onTime={setClimateTime}
                onPlaying={setPlayingClimate}
              />
            )}
            {source.kind === "scenario" && source.field === CLIMATE_FIELD && (
              <HouseAir state={houseAir} />
            )}
            {source.kind === "scenario" && source.field === CLIMATE_FIELD && (
              <ClimateSchedule
                schedule={source.schedule ?? []}
                time={fieldTime}
                onTime={setClimateTime}
                onRemove={removeCommand}
              />
            )}
            {source.kind === "scenario" && (
              <WeatherPanel
                state={weather}
                day={weatherDay}
                weathers={
                  scenarios.status === "loaded"
                    ? (scenarios.scenarios.find((s) => s.id === source.scenarioId)?.weathers ?? [])
                    : []
                }
                chosen={source.weather}
                time={fieldTime}
                onChoose={chooseWeather}
              />
            )}
            {source.kind === "scenario" && source.field !== undefined && probedField !== null && (
              <FieldProbes
                scenarioId={source.scenarioId}
                layout={source.layout}
                fieldName={source.field}
                field={probedField}
                compareName={source.compare ?? null}
                compareState={compared}
                probes={probes}
                placing={placingProbes}
                height={probeHeight}
                onProbes={setProbes}
                onCompare={compareWith}
                onPlacing={setPlacingProbes}
                onHeight={setProbeHeight}
              />
            )}
            {source.kind === "scenario" && source.field === CLIMATE_FIELD && (
              <ProbeCharts state={probeCharts} time={fieldTime} />
            )}
            {source.kind === "scenario" && (
              <CfdControls
                shown={source.cfdBoundaries === true}
                state={cfd}
                onShow={showCfdBoundaries}
              />
            )}
            {snapshot !== null && source.kind === "scenario" && (
              <OpeningControls
                snapshot={snapshot}
                requested={source.openings ?? {}}
                onChange={setOpenings}
              />
            )}
            {snapshot !== null && source.kind === "scenario" && (
              <EquipmentControls
                snapshot={snapshot}
                requested={levelsAt(source)}
                onChange={setLevels}
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
            >
              {snapshot !== null && selectedCamera !== null && (
                <>
                  <CameraView snapshot={snapshot} spec={selectedCamera} />
                  <CameraFrames cameraId={selectedCamera.cameraId} state={sensorReadings} />
                </>
              )}
              {selected.kind === "SENSOR" && (
                <SensorPanel
                  sensorId={String(selected.properties.sensor_id)}
                  unit={String(selected.properties.unit)}
                  state={sensorReadings}
                  allOff={offReadings}
                  until={fieldTime}
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
            onPreset={choosePreset}
            onCommand={command}
          />
          <div className="legends">
            {byCategory && snapshot !== null && (
              <CategoryLegend categories={categoriesIn(snapshot)} />
            )}
            {colouring && <ScalarLegend colouring={colouring} />}
            {cfd.status === "loaded" && <CfdLegend geometry={cfd.geometry} />}
            {fieldScale !== null && (
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
