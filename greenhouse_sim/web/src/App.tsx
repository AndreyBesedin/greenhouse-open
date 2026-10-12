import { useEffect, useMemo, useState } from "react";

import { type BuildInfo, buildInfo } from "./buildInfo";
import type { PresetName, PresetRequest } from "./camera";
import { CfdBoundaries } from "./cfd/CfdBoundaries";
import { CfdLegend } from "./cfd/CfdLegend";
import { cfdGeometryUrl, loadCfdGeometry } from "./cfd/geometry";
import { DisplayOptions } from "./DisplayOptions";
import { CategoryLegend } from "./debug/CategoryLegend";
import { categoriesIn } from "./debug/categories";
import { sceneDimensionOverlays } from "./debug/dimensions";
import { ALL_OVERLAYS, type OverlayToggles, selectionOverlays } from "./debug/overlays";
import { ScalarLegend } from "./debug/ScalarLegend";
import type { ScalarRange } from "./debug/scalar";
import { colouringBy, scalarProperties } from "./debug/scalar";
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
import type { GrowthSpeed } from "./plants/LabControls";
import { LabPanels } from "./plants/LabPanels";
import { type LabRun, PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "./plants/lab";
import { loadPlantsLight, plantsLightUrl } from "./plants/light";
import { plantNameOverlays } from "./plants/names";
import { PlantLight } from "./plants/PlantLight";
import type { ViewSample } from "./readouts";
import { ScenarioPanels } from "./ScenarioPanels";
import { loadScenarios, SCENARIOS_URL } from "./scenarios";
import { withProbes } from "./scene/edits";
import { runApartFromItsMoment, runsSomething, scenarioRun } from "./scene/run";
import {
  changesQuery,
  loadScene,
  type SceneSource,
  sceneRequest,
  withItsAir,
} from "./scene/source";
import { useLiveCommands } from "./scene/useLiveCommands";
import { useLiveScene } from "./scene/useLiveScene";
import { useSource } from "./scene/useSource";
import { entityOfOrgan, selectedEntity } from "./selection";
import { CameraFrames } from "./sensors/CameraFrames";
import { CameraView } from "./sensors/CameraView";
import { cameraOf, frustumOverlays } from "./sensors/camera";
import { loadSensorReadings, sensorsKey } from "./sensors/readings";
import { SensorPanel } from "./sensors/SensorPanel";
import { useLoad } from "./useLoad";
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

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  const [source, setSource] = useSource();
  // Whether a click places a probe, and how high.
  const [placingProbes, setPlacingProbes] = useState(false);
  const [playingClimate, setPlayingClimate] = useState(false);
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
  const scenarios = useLoad(SCENARIOS_URL, () => loadScenarios());
  // The scenario shown, as the list describes it: its weathers and its days.
  const summary =
    source.kind === "scenario" && scenarios.status === "loaded"
      ? scenarios.scenarios.find((s) => s.id === source.scenarioId)
      : undefined;

  // A scenario reopened by its sliders, or the plant lab on another day,
  // keeps its scene on show until the next arrives; any other change of
  // scene starts from loading.
  const sceneAsked = sceneRequest(source);
  const scene = useLoad(sceneAsked, () => loadScene(source), {
    group:
      source.kind === "scenario"
        ? `scenario ${source.scenarioId}`
        : source.kind === "plants"
          ? "plants"
          : (sceneAsked ?? ""),
  });

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

  // The scenario's field, drawn over its scene, and another compared with it
  // at the probes; the last of each stays on show until the next arrives.
  const fieldName = source.kind === "scenario" ? (source.field ?? null) : null;
  const field = useLoad(
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
  const compareName = source.kind === "scenario" ? (source.compare ?? null) : null;
  const compared = useLoad(
    run === null || compareName === null ? null : fieldUrl(run.scenarioId, compareName, run),
    fetchField,
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

  function chooseSource(chosen: SceneSource): void {
    const next = withItsAir(source, chosen);
    commands.forget();
    setSource(next);
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
  // The light on the plants at the moment drawn, while a plant is selected
  // in a climate run's view; the last stays on show until the next arrives.
  const plantsLight = useLoad(
    climate === null || selected?.kind !== "PLANT"
      ? null
      : plantsLightUrl(climate.scenarioId, moment, climate.weather, climate.layout),
    loadPlantsLight,
  );
  const selectedCamera = selected === null ? null : cameraOf(selected);

  // The run's observation log up to the moment drawn, and what its sensors
  // truly sampled, while a sensor or a camera is selected.
  const sensorSelected = selected?.kind === "SENSOR" || selected?.kind === "CAMERA";
  const sensorRun = sensorSelected ? run : null;
  const sensorReadings = useLoad(
    sensorRun === null
      ? null
      : { scenarioId: sensorRun.scenarioId, run: { ...sensorRun, clean: !sensorsImperfect } },
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
            daily: undefined,
            clean: !sensorsImperfect,
          },
        },
    loadSensorReadings,
    { key: sensorsKey },
  );

  const showingNames = source.kind === "plants" && showPlantNames;
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
  const overlays = useMemo(
    () => [
      ...(selected === null ? [] : selectionOverlays(selected, overlayToggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames ? plantNameOverlays(snapshot) : []),
      ...(probedField === null ? [] : probeOverlays(probes, probedField)),
      ...(snapshot === null ? [] : frustumOverlays(snapshot)),
      ...(snapshot === null || outside === null ? [] : windOverlays(snapshot, outside)),
      ...(snapshot === null || outside === null ? [] : sunOverlays(snapshot, outside)),
      ...(snapshot === null || sunsDay === null ? [] : sunPathOverlays(snapshot, sunsDay)),
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
      sunsDay,
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
              <ScenarioPanels
                source={source}
                snapshot={snapshot}
                weathers={summary?.weathers ?? []}
                days={summary?.duration_days ?? 1}
                loads={{ field, compared, weather, weatherDay, houseAir, probeCharts, cfd }}
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
              {selected.kind === "PLANT" && (
                <PlantLight plantId={selected.entity_id} state={plantsLight} />
              )}
              {selected.kind === "SENSOR" && (
                <SensorPanel
                  sensorId={String(selected.properties.sensor_id)}
                  unit={String(selected.properties.unit)}
                  state={sensorReadings}
                  allOff={offReadings}
                  until={moment}
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
            onCommand={commands.send}
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
