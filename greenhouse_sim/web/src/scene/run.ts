import { layoutText } from "./moves";
import {
  apiWeather,
  type CropCommand,
  cropText,
  dailyText,
  pairsText,
  type SceneSource,
  type ScheduledCommand,
  scheduleText,
  type TargetChange,
  targetsText,
  weatherParameter,
} from "./source";

/** The parts of a scenario's run the simulator is asked for each part of it
 * by: another of its layouts, its equipment's levels from the start, how far
 * its doors and vents stand open, the commands after the start, the moment
 * drawn, and the weather it runs under, as the API names it. */
export interface RunParts {
  layout?: string | undefined;
  levels?: Readonly<Record<string, number>> | undefined;
  openings?: Readonly<Record<string, number>> | undefined;
  /** Commands to its equipment after the start. */
  schedule?: readonly ScheduledCommand[] | undefined;
  /** Commands at a time of day, every day of the run. */
  daily?: readonly ScheduledCommand[] | undefined;
  /** Changes to its targets, each from a moment on (#274). */
  targets?: readonly TargetChange[] | undefined;
  /** Actions on its crop, each at a day's start (P13.8). */
  crop?: readonly CropCommand[] | undefined;
  /** Seconds into the climate run. */
  time?: number | undefined;
  /** Another weather the run is under, a preset's by name, its clouds
   * overridden as `apiWeather` writes it. */
  weather?: string | undefined;
}

/** A scenario's run, as the viewer draws it. */
export interface ScenarioRun extends RunParts {
  scenarioId: string;
}

export type RunPart = keyof RunParts;

/** Every part, as the climate's routes take them. */
export const CLIMATE_PARTS: readonly RunPart[] = [
  "layout",
  "levels",
  "openings",
  "schedule",
  "daily",
  "targets",
  "crop",
  "time",
  "weather",
];

/** The run a scenario's source draws: its parts as its address holds them,
 * and its weather with the clouds and the wind asked for. */
export function scenarioRun(source: Extract<SceneSource, { kind: "scenario" }>): ScenarioRun {
  return {
    scenarioId: source.scenarioId,
    layout: source.layout,
    levels: source.levels,
    openings: source.openings,
    schedule: source.schedule,
    daily: source.daily,
    targets: source.targets,
    crop: source.crop,
    time: source.time,
    weather: apiWeather(source.weather, source.clouds, source.wind),
  };
}

/** A run's parts as a route's query takes them, in this order: `layout=`,
 * `set=`, `open=`, `schedule=`, `daily=`, `targets=`, `crop=`, `t=` and
 * `weather=`. A part not given, or not among `parts`, is left out, and so is
 * the run's start, `t=0`. */
export function runParameters(run: RunParts, parts: readonly RunPart[] = CLIMATE_PARTS): string[] {
  const asked = new Set(parts);
  const levels = asked.has("levels") ? pairsText(run.levels) : "";
  const openings = asked.has("openings") ? pairsText(run.openings) : "";
  const schedule = asked.has("schedule") ? scheduleText(run.schedule) : "";
  const daily = asked.has("daily") && run.daily !== undefined ? dailyText(run.daily) : "";
  const targets = asked.has("targets") ? targetsText(run.targets) : "";
  const crop = asked.has("crop") ? cropText(run.crop) : "";
  const time = asked.has("time") && run.time !== undefined && run.time > 0 ? run.time : null;
  return [
    ...(asked.has("layout") && run.layout !== undefined
      ? [`layout=${layoutText(run.layout)}`]
      : []),
    ...(levels === "" ? [] : [`set=${levels}`]),
    ...(openings === "" ? [] : [`open=${openings}`]),
    ...(schedule === "" ? [] : [`schedule=${schedule}`]),
    ...(daily === "" ? [] : [`daily=${daily}`]),
    ...(targets === "" ? [] : [`targets=${targets}`]),
    ...(crop === "" ? [] : [`crop=${crop}`]),
    ...(time === null ? [] : [`t=${time}`]),
    ...(asked.has("weather") ? weatherParameter(run.weather) : []),
  ];
}

/** A scenario's route, with its query's parameters, if any. */
export function scenarioUrl(scenarioId: string, path: string, parameters: string[]): string {
  const query = parameters.length === 0 ? "" : `?${parameters.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/${path}${query}`;
}

/** What tells one run from another, apart from the moment drawn: through a
 * run's moments its colours keep the widest range they have reached. */
export function runApartFromItsMoment(run: ScenarioRun): string {
  return scenarioUrl(run.scenarioId, "run", runParameters({ ...run, time: undefined }));
}

/** Whether the run's equipment does anything: levels from the start, or
 * commands after it, once or every day. */
export function runsSomething(run: RunParts): boolean {
  return (
    pairsText(run.levels) !== "" ||
    scheduleText(run.schedule) !== "" ||
    scheduleText(run.daily) !== ""
  );
}
