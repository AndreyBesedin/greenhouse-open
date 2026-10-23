import { type ReactNode, useCallback, useState } from "react";

import { CfdControls } from "./cfd/CfdControls";
import type { CfdGeometryState } from "./cfd/geometry";
import { BranchComparison } from "./checkpoints/BranchComparison";
import { checkpointRun, comparable } from "./checkpoints/branches";
import { CheckpointsPanel } from "./checkpoints/CheckpointsPanel";
import { type CheckpointSummary, restored } from "./checkpoints/checkpoints";
import { EquipmentControls, equipmentIn } from "./EquipmentControls";
import { ClimateSchedule } from "./fields/ClimateSchedule";
import { ClimateTime, describeClimateRun } from "./fields/ClimateTime";
import type { FieldView, Slice } from "./fields/display";
import { describeAirField, FieldControls, useFieldNames } from "./fields/FieldControls";
import { describeProbes, FieldProbes } from "./fields/FieldProbes";
import { describeHouseAir, HouseAir, type HouseAirState } from "./fields/HouseAir";
import { ProbeCharts, type ProbeChartsState } from "./fields/ProbeCharts";
import { CLIMATE_FIELD, type FieldState } from "./fields/source";
import { TargetsPanel } from "./fields/TargetsPanel";
import { useFolds } from "./folds";
import { OpeningControls, openingsIn } from "./OpeningControls";
import { PanelCard } from "./PanelCard";
import {
  levelsAt,
  openingsAt,
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
 * A scenario's panels, in the info panel's order: its air field and CFD
 * boundaries, its climate run's moment, house air, schedule, timeline and
 * checkpoints, its weather, the probes and their charts, and its doors,
 * vents and equipment, each a section folded to its line but the moment
 * (#206, #273). Each changes the scenario's source; what the view around
 * them keeps (how the field's colours run, whether a click places a probe)
 * is the viewer's.
 */
export function ScenarioPanels({
  children,
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
  setpoints,
  onTargets,
  onSource,
  onProbes,
  onPlacing,
  onProbeHeight,
  onPlayingClimate,
  onOwnRange,
}: {
  /** What leads the simulation's card: the run played back, while the view
   * follows it. */
  children?: ReactNode;
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
  /** Its thermostat at the moment drawn, whether or not it runs its heater
   * then, with its setpoints: undefined if the scenario has none, null while
   * they are on their way (#274). */
  setpoints?: ThermostatAt | null | undefined;
  /** Changes its heating targets from the moment drawn on (#274). */
  onTargets?: (targets: Record<string, number>) => void;
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
  // The moment drawn, which stays while another is on its way or failed.
  const shownTime = probed === null ? null : probed.timeS;
  // Every group folded to the line that says how it stands (#206, #273):
  // the climate run's moment open at first, the rest folded.
  const fold = useFolds<"field" | "moment" | "house" | "equipment" | "openings" | "probes">([
    "moment",
  ]);
  const fieldName = source.field;
  const probing = fieldName !== undefined && probed !== null;

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

  // Whether the run played back leads the simulation's card: a JSX `false`
  // when the view does not follow one.
  const leads = children !== undefined && children !== null && children !== false;
  // A card is drawn only with a section in it: a scenario may have no
  // openings, no equipment or no weather.
  const openings = snapshot === null ? [] : openingsIn(snapshot);
  const equipped = snapshot !== null && equipmentIn(snapshot).length > 0;
  // The sections grouped in titled cards by topic (#306): the run played
  // back and the climate run's moment and course; the house's air, its
  // targets and its schedule; its equipment, openings and probes; and the
  // weather outside.
  return (
    <>
      {(leads || climate) && (
        <PanelCard title="Simulation">
          {children}
          {climate && (
            <details className="moment-fold" {...fold("moment")}>
              <summary data-testid="moment-summary">
                {describeClimateRun(time, shownTime, momentFailed)}
              </summary>
              <ClimateTime
                time={time}
                shown={shownTime}
                failed={momentFailed}
                followed={source.follow === true}
                days={days}
                playing={playingClimate}
                onTime={setTime}
                onPlaying={onPlayingClimate}
              />
            </details>
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
        </PanelCard>
      )}
      <PanelCard title="House">
        <details className="field-fold" {...fold("field")}>
          <summary data-testid="field-summary">
            {describeAirField(source.field ?? null, fieldView, source.cfdBoundaries === true)}
          </summary>
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
          <CfdControls
            shown={source.cfdBoundaries === true}
            state={cfd}
            onShow={(show) => onSource(withCfdBoundaries(source, show))}
          />
        </details>
        {climate && (
          <details className="house-fold" {...fold("house")}>
            <summary data-testid="house-summary">{describeHouseAir(houseAir)}</summary>
            <HouseAir state={houseAir} />
          </details>
        )}
        {climate && setpoints !== undefined && onTargets !== undefined && (
          <TargetsPanel
            thermostat={setpoints}
            time={time}
            followed={source.follow === true}
            onSet={onTargets}
          />
        )}
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
      </PanelCard>
      {(probing || climate || openings.length > 0 || equipped) && (
        <PanelCard title="Equipment">
          {(probing || climate) && (
            <details className="probes-fold" {...fold("probes")}>
              <summary data-testid="probes-summary">
                {describeProbes(probes.length, source.compare ?? null)}
              </summary>
              {probing && (
                <FieldProbes
                  names={fields.names}
                  fieldName={fieldName}
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
            </details>
          )}
          {snapshot !== null && (
            <OpeningControls
              snapshot={snapshot}
              requested={openingsAt(
                source,
                openings.map((opening) => opening.openingId),
              )}
              fold={fold("openings")}
              onChange={(openings) => onSource(withOpenings(source, openings))}
            />
          )}
          {snapshot !== null && (
            <EquipmentControls
              snapshot={snapshot}
              requested={levelsAt(source)}
              thermostat={thermostat}
              fold={fold("equipment")}
              onChange={(levels) => onSource(withLevels(source, levels))}
            />
          )}
        </PanelCard>
      )}
      {weather.status !== "none" && (
        <PanelCard title="Outside">
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
        </PanelCard>
      )}
    </>
  );
}
