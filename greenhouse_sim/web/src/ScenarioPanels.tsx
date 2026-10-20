import { useCallback, useState } from "react";

import { CfdControls } from "./cfd/CfdControls";
import type { CfdGeometryState } from "./cfd/geometry";
import { BranchComparison } from "./checkpoints/BranchComparison";
import { checkpointRun, comparable } from "./checkpoints/branches";
import { CheckpointsPanel } from "./checkpoints/CheckpointsPanel";
import { type CheckpointSummary, restored } from "./checkpoints/checkpoints";
import { EquipmentControls } from "./EquipmentControls";
import { ClimateSchedule } from "./fields/ClimateSchedule";
import { ClimateTime } from "./fields/ClimateTime";
import type { FieldView, Slice } from "./fields/display";
import { FieldControls, useFieldNames } from "./fields/FieldControls";
import { FieldProbes } from "./fields/FieldProbes";
import { HouseAir, type HouseAirState } from "./fields/HouseAir";
import { ProbeCharts, type ProbeChartsState } from "./fields/ProbeCharts";
import { CLIMATE_FIELD, type FieldState } from "./fields/source";
import { OpeningControls, openingsIn } from "./OpeningControls";
import {
  type ScenarioSource,
  withCfdBoundaries,
  withClouds,
  withCompared,
  withField,
  withFieldView,
  withLevels,
  withOpenings,
  withoutCommand,
  withoutDaily,
  withRepeated,
  withSlice,
  withTime,
  withWeather,
  withWind,
} from "./scene/edits";
import type { ThermostatAt } from "./scene/equipment";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { scenarioRun } from "./scene/run";
import { levelsAt, openingsAt } from "./scene/source";
import type { SetSource } from "./scene/useSource";
import { TimelinePanel } from "./timeline/TimelinePanel";
import { WeatherPanel } from "./weather/WeatherPanel";
import type { WeatherDayState, WeatherStateOfLoad } from "./weather/weather";
import type { Point3 } from "./world";

/** What the viewer has loaded of a scenario's run, for its panels. */
export interface ScenarioLoads {
  field: FieldState;
  compared: FieldState;
  weather: WeatherStateOfLoad;
  weatherDay: WeatherDayState;
  houseAir: HouseAirState;
  probeCharts: ProbeChartsState;
  cfd: CfdGeometryState;
}

/**
 * A scenario's panels, in the info panel's order: its fields, its climate
 * run's moment, house air, schedule, timeline and checkpoints, its weather, the probes and their
 * charts, its CFD boundaries, and its doors, vents and equipment. Each
 * changes the scenario's source; what the view around them keeps (how the
 * field's colours run, whether a click places a probe) is the viewer's.
 */
export function ScenarioPanels({
  source,
  snapshot,
  weathers,
  days,
  loads,
  momentFailed = false,
  fieldView,
  fieldSlice,
  probes,
  placing,
  probeHeight,
  playingClimate,
  thermostat = null,
  onSource,
  onProbes,
  onPlacing,
  onProbeHeight,
  onPlayingClimate,
  onOwnRange,
}: {
  source: ScenarioSource;
  snapshot: SceneSnapshot | null;
  /** The preset weathers it can be run under. */
  weathers: string[];
  /** How many days its runs last. */
  days: number;
  loads: ScenarioLoads;
  /** Whether the moment asked for cannot be drawn, part of it having failed
   * to arrive. */
  momentFailed?: boolean;
  fieldView: FieldView;
  fieldSlice: Slice | null;
  probes: Point3[];
  placing: boolean;
  probeHeight: number;
  playingClimate: boolean;
  /** The thermostat that runs its heater at the moment drawn, if one does. */
  thermostat?: ThermostatAt | null;
  onSource: (change: SetSource) => void;
  onProbes: (probes: Point3[]) => void;
  onPlacing: (placing: boolean) => void;
  onProbeHeight: (height: number) => void;
  onPlayingClimate: (playing: boolean) => void;
  /** The field's colours go back to its own range. */
  onOwnRange: () => void;
}) {
  const { field, compared: comparedField, weather, weatherDay, houseAir, probeCharts, cfd } = loads;
  // The checkpoint whose run is compared with the run drawn, if one is.
  const [against, setAgainst] = useState<CheckpointSummary | null>(null);
  // Asked for once, for the field's choice and what it is compared with.
  const fields = useFieldNames(source.scenarioId, source.layout);
  const climate = source.field === CLIMATE_FIELD;
  const time = source.time ?? 0;
  const probed = field.status === "loaded" ? field.field : null;

  // The moment changes from the source as it is then: playing, the climate
  // run moves on render after render.
  const setTime = useCallback(
    (seconds: number) =>
      onSource((current) => (current.kind === "scenario" ? withTime(current, seconds) : current)),
    [onSource],
  );

  function chooseField(name: string | null): void {
    onOwnRange();
    if (name === null) {
      onPlacing(false);
    }
    onSource(withField(source, name));
  }

  function chooseFieldView(view: FieldView): void {
    if (field.status !== "loaded") {
      return;
    }
    onOwnRange();
    onSource(withFieldView(source, view, field.field));
  }

  function chooseSlice(slice: Slice): void {
    if (source.slice?.quantity !== slice.quantity) {
      onOwnRange();
    }
    onSource(withSlice(source, slice));
  }

  return (
    <>
      <FieldControls
        fields={fields}
        chosen={source.field ?? null}
        state={field}
        view={fieldView}
        slice={fieldSlice}
        onChoose={chooseField}
        onView={chooseFieldView}
        onSlice={chooseSlice}
      />
      {climate && (
        <ClimateTime
          time={time}
          shown={field.status === "loaded" ? field.field.timeS : null}
          failed={momentFailed}
          days={days}
          playing={playingClimate}
          onTime={setTime}
          onPlaying={onPlayingClimate}
        />
      )}
      {climate && <HouseAir state={houseAir} />}
      {climate && (
        <ClimateSchedule
          schedule={source.schedule ?? []}
          daily={source.daily ?? []}
          time={time}
          days={days}
          onTime={setTime}
          onRemove={(index) => onSource(withoutCommand(source, index))}
          onRepeat={(index) => onSource(withRepeated(source, index))}
          onRemoveDaily={(index) => onSource(withoutDaily(source, index))}
        />
      )}
      {climate && (
        <TimelinePanel scenarioId={source.scenarioId} run={scenarioRun(source)} time={time} />
      )}
      {climate && (
        <CheckpointsPanel
          scenarioId={source.scenarioId}
          run={scenarioRun(source)}
          time={time}
          onRestore={(checkpoint) => onSource(restored(source, checkpoint, CLIMATE_FIELD))}
          compared={against?.checkpointId ?? null}
          onCompare={setAgainst}
        />
      )}
      {climate && against !== null && against.scenarioId === source.scenarioId && (
        <BranchComparison
          checkpoint={against}
          time={time}
          request={{
            scenarioId: source.scenarioId,
            a: checkpointRun(against, time),
            b: scenarioRun(source),
            fromDay: against.day,
            ...comparable(snapshot),
          }}
        />
      )}
      <WeatherPanel
        state={weather}
        day={weatherDay}
        weathers={weathers}
        chosen={source.weather}
        time={time}
        onChoose={(chosen) => onSource(withWeather(source, chosen))}
        clouds={source.clouds}
        onClouds={(clouds) => onSource(withClouds(source, clouds))}
        windFrom={source.wind}
        onWindFrom={(wind) => onSource(withWind(source, wind))}
      />
      {source.field !== undefined && probed !== null && (
        <FieldProbes
          names={fields.names}
          fieldName={source.field}
          field={probed}
          compareName={source.compare ?? null}
          compareState={comparedField}
          probes={probes}
          placing={placing}
          height={probeHeight}
          onProbes={onProbes}
          onCompare={(name) => onSource(withCompared(source, name))}
          onPlacing={onPlacing}
          onHeight={onProbeHeight}
        />
      )}
      {climate && <ProbeCharts state={probeCharts} time={time} />}
      <CfdControls
        shown={source.cfdBoundaries === true}
        state={cfd}
        onShow={(show) => onSource(withCfdBoundaries(source, show))}
      />
      {snapshot !== null && (
        <OpeningControls
          snapshot={snapshot}
          requested={openingsAt(
            source,
            openingsIn(snapshot).map((opening) => opening.openingId),
          )}
          onChange={(openings) => onSource(withOpenings(source, openings))}
        />
      )}
      {snapshot !== null && (
        <EquipmentControls
          snapshot={snapshot}
          requested={levelsAt(source)}
          thermostat={thermostat}
          onChange={(levels) => onSource(withLevels(source, levels))}
        />
      )}
    </>
  );
}
