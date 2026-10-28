/**
 * Which scene the viewer draws (`SceneSource`), and how the address bar and
 * the simulator's API write its parts: the address's codec (`searchFor`,
 * `sourceFromSearch`), and the texts both write the same way. The helpers
 * that edit a source are in `edits.ts`, and loading its scene in
 * `sceneLoad.ts`.
 */
import type { CameraPose } from "../camera";
import { type FieldView, fieldViewFrom, type Slice, sliceFrom, sliceText } from "../fields/display";
import { probesFrom, probesText } from "../fields/probes";
import {
  actionFrom,
  actionsQuery,
  FIRST_LAB_RUN,
  type LabRun,
  PLANT_LAB_LAST_DAY,
  PLANT_LAB_SEED,
} from "../plants/lab";
import { stressPlants } from "../qa/stressScene";
import { DEFAULT_WEATHER } from "../scenarios";
import type { Point3 } from "../world";
import { layoutText } from "./moves";

/** Which scene the viewer draws, chosen in the address bar so a refresh keeps it. */
export type SceneSource =
  | { kind: "reference" }
  | { kind: "example" }
  /** One fixture of each primitive, side by side, as the simulator draws them. */
  | { kind: "fixtures" }
  /** The plant lab: a row of tomato plants from the organ-level model, on a
   * run of the lab. */
  | ({ kind: "plants" } & LabRun)
  /** A dense field of plants built in the viewer, for measuring the renderer. */
  | { kind: "stress"; plants: number }
  /** A scenario's scene from the simulator, with another of its layouts if
   * `layout` names one, its greenhouse's dimensions changed as `envelope`
   * asks (length, width, spans, bays, eave_height, ridge_height), its doors
   * and vents opened as `openings` asks (by opening identifier, from 0 to 1),
   * and its equipment run as `levels` asks (by actuator, from 0 to 1). */
  | {
      kind: "scenario";
      scenarioId: string;
      layout?: string;
      /** Another weather it is run under, a preset's by name, in place of
       * its own. */
      weather?: string;
      /** A QA override of its weather's cloud cover, in %, which dims its
       * light as such a sky would. */
      clouds?: number;
      /** A QA override of the wind's direction, the bearing it blows from. */
      wind?: number;
      /** One of its environment fields, drawn over its scene, as arrows by
       * default, and where a slice through it lies, if one is drawn. */
      field?: string;
      fieldView?: FieldView;
      slice?: Slice;
      /** How far into its climate run the drawn field is, in seconds, for
       * its climate. */
      time?: number;
      /** Commands to its equipment after the start of its climate run, in
       * the order given: its schedule and the overrides made. */
      schedule?: ScheduledCommand[];
      /** Commands at a time of day, every day of its climate run, each
       * `timeS` its time of day, in the order given (P09.2). */
      daily?: ScheduledCommand[];
      /** Changes to its targets, each from a moment on, in the order given
       * (#274, decision 0043). */
      targets?: TargetChange[];
      /** Actions on its crop, each at a day's start, in the order given
       * (P13.8). */
      crop?: CropCommand[];
      /** Another of its fields, compared with the drawn one at the probes. */
      compare?: string;
      /** Points the drawn field is read at. */
      probes?: Point3[];
      /** Whether the boundaries a CFD solver is given are drawn over it. */
      cfdBoundaries?: true;
      /** Where the camera starts, rather than the default preset: for a part
       * of a big greenhouse no preset frames. */
      camera?: CameraPose;
      /** Whether its moment follows the clock of its own run played back
       * (P10.2, decision 0041), rather than being set here. */
      follow?: true;
      envelope?: Readonly<Record<string, number>>;
      openings?: Readonly<Record<string, number>>;
      levels?: Readonly<Record<string, number>>;
    };

/** A change to one of a run's targets, such as its heating setpoint by
 * day, from a moment of its climate run on, in °C (#274). */
export interface TargetChange {
  timeS: number;
  target: string;
  valueC: number;
}

/** An action on a run's crop at a moment of it, as the address spells it
 * (P13.8): its plant, its kind (`remove_leaf`, `harvest_fruit`,
 * `harvest_truss`, `lower_stem`, ...) and what it acts on, as the
 * simulator's `&crop=` takes them. */
export interface CropCommand {
  timeS: number;
  plantId: string;
  kind: string;
  target: string;
}

/** A command to a piece of equipment at a moment of a climate run. */
export interface ScheduledCommand {
  timeS: number;
  actuatorId: string;
  level: number;
}

// The address's `cfd=` when a scenario's CFD boundaries are drawn.
const CFD_BOUNDARIES = "boundaries";
// The most a sky can be clouded, in %, and how the simulator is asked for a
// weather under other clouds than its own: `cold_spring_day@80`.
const MOST_CLOUDS_PCT = 100;
const CLOUDS_MARK = "@";
// And then a wind's direction in place of its own: `default~90`.
const WIND_MARK = "~";
const FULL_TURN_DEG = 360;

export function sourceFromSearch(search: string): SceneSource {
  const parameters = new URLSearchParams(search);
  // The live mode's address opens the scenario's run, followed as it is
  // played back, which took its place (decision 0059).
  const liveId = parameters.get("live");
  if (liveId) {
    return { kind: "scenario", scenarioId: liveId, follow: true };
  }
  const scenarioId = parameters.get("scenario");
  if (scenarioId) {
    const layout = parameters.get("layout");
    const weather = parameters.get("weather");
    const clouds = cloudsFrom(parameters.get("clouds"));
    const wind = windFrom(parameters.get("wind"));
    const envelope = pairsFrom(parameters.get("envelope"));
    const openings = pairsFrom(parameters.get("open"));
    const levels = pairsFrom(parameters.get("set"));
    const field = parameters.get("field");
    const fieldView = fieldViewFrom(parameters.get("fieldView"));
    const slice = sliceFrom(parameters.get("slice"));
    const compare = parameters.get("compare");
    const time = timeFrom(parameters.get("t"));
    const schedule = scheduleFrom(parameters.get("schedule"));
    const daily = dailyFrom(parameters.get("daily"));
    const targets = targetsFrom(parameters.get("targets"));
    const crop = cropFrom(parameters.get("crop"));
    const probes = probesFrom(parameters.get("probes"));
    const camera = cameraFrom(parameters.get("camera"));
    return {
      kind: "scenario",
      scenarioId,
      ...(layout ? { layout } : {}),
      ...(weather ? { weather } : {}),
      ...(clouds === null ? {} : { clouds }),
      ...(wind === null ? {} : { wind }),
      ...(field ? { field } : {}),
      ...(field && fieldView ? { fieldView } : {}),
      ...(field && slice ? { slice } : {}),
      ...(field && time !== null ? { time } : {}),
      ...(field && schedule !== null ? { schedule } : {}),
      ...(field && daily !== null ? { daily } : {}),
      ...(field && targets !== null ? { targets } : {}),
      ...(crop !== null ? { crop } : {}),
      ...(field && compare && compare !== field ? { compare } : {}),
      ...(field && probes ? { probes } : {}),
      ...(parameters.get("cfd") === CFD_BOUNDARIES ? { cfdBoundaries: true as const } : {}),
      ...(camera === undefined ? {} : { camera }),
      ...(parameters.get("follow") === "1" ? { follow: true as const } : {}),
      ...(envelope === null ? {} : { envelope }),
      ...(openings === null ? {} : { openings }),
      ...(levels === null ? {} : { levels }),
    };
  }
  if (parameters.get("plants") === "lab") {
    return {
      kind: "plants",
      day: labDay(parameters.get("day")),
      seed: labSeed(parameters.get("seed")),
      environment: parameters.get("environment") || FIRST_LAB_RUN.environment,
      versus: parameters.get("versus") || null,
      actions: parameters
        .getAll("act")
        .map(actionFrom)
        .filter((action) => action !== null),
    };
  }
  switch (parameters.get("scene")) {
    case "example":
      return { kind: "example" };
    case "fixtures":
      return { kind: "fixtures" };
    case "stress":
      return { kind: "stress", plants: stressPlants(parameters.get("plants")) };
    default:
      return { kind: "reference" };
  }
}

/** The plant lab's day an address asks for: a whole number of days within
 * the lab's run, or its first day. */
function labDay(text: string | null): number {
  const day = Number(text ?? "0");
  return Number.isInteger(day) && day >= 0 && day <= PLANT_LAB_LAST_DAY ? day : 0;
}

/** The plant lab's seed an address asks for: a whole number from 0, or the
 * lab's own. */
function labSeed(text: string | null): number {
  const seed = Number(text ?? "");
  return text !== null && Number.isSafeInteger(seed) && seed >= 0 ? seed : PLANT_LAB_SEED;
}

/** A run of the plant lab as the address bar writes it, leaving out what is
 * as the lab starts. */
function labQuery(run: LabRun, separator: "?" | "&"): string {
  const parts = [
    ...(run.day === FIRST_LAB_RUN.day ? [] : [`day=${run.day}`]),
    ...(run.seed === FIRST_LAB_RUN.seed ? [] : [`seed=${run.seed}`]),
    ...(run.environment === FIRST_LAB_RUN.environment
      ? []
      : [`environment=${encodeURIComponent(run.environment)}`]),
    ...(run.versus === null ? [] : [`versus=${encodeURIComponent(run.versus)}`]),
    ...actionsQuery(run.actions),
  ];
  return parts.length === 0 ? "" : `${separator}${parts.join("&")}`;
}

/**
 * What a source shows, apart from where in it and how: a scene, the plant
 * lab, or a scenario and its layout. Another of these
 * is a new page in the browser's history, so that Back returns to the view
 * before it (#201); a change within one, a moment, a field or a command,
 * replaces the page.
 */
export function shownBy(source: SceneSource): string {
  switch (source.kind) {
    case "scenario":
      return `scenario ${source.scenarioId} ${source.layout ?? ""}`;
    default:
      return source.kind;
  }
}

export function searchFor(source: SceneSource): string {
  switch (source.kind) {
    case "reference":
      return "";
    case "example":
      return "?scene=example";
    case "fixtures":
      return "?scene=fixtures";
    case "plants":
      return `?plants=lab${labQuery(source, "&")}`;
    case "stress":
      return `?scene=stress&plants=${source.plants}`;
    case "scenario":
      return `?scenario=${encodeURIComponent(source.scenarioId)}${changesQuery(source, "&")}${weatherParameter(
        source.weather,
      )
        .map((part) => `&${part}`)
        .join(
          "",
        )}${source.clouds === undefined ? "" : `&clouds=${source.clouds}`}${source.wind === undefined ? "" : `&wind=${source.wind}`}${fieldQuery(source)}${source.crop === undefined || source.crop.length === 0 ? "" : `&crop=${cropText(source.crop)}`}${source.cfdBoundaries ? `&cfd=${CFD_BOUNDARIES}` : ""}${source.camera === undefined ? "" : `&camera=${cameraText(source.camera)}`}${source.follow ? "&follow=1" : ""}`;
  }
}

/** `weather=` for another weather a scenario is run under, or nothing for
 * its own. The address bar and the simulator's API write it the same way. */
export function weatherParameter(weather: string | undefined): string[] {
  return weather === undefined ? [] : [`weather=${encodeURIComponent(weather)}`];
}

/** How a scenario's field is drawn, compared and probed, as the address bar
 * writes it. */
function fieldQuery(source: {
  field?: string;
  fieldView?: FieldView;
  slice?: Slice;
  time?: number;
  schedule?: ScheduledCommand[];
  daily?: ScheduledCommand[];
  targets?: TargetChange[];
  compare?: string;
  probes?: Point3[];
}): string {
  if (source.field === undefined) {
    return "";
  }
  return [
    `&field=${encodeURIComponent(source.field)}`,
    source.fieldView === undefined ? "" : `&fieldView=${source.fieldView}`,
    source.slice === undefined ? "" : `&slice=${sliceText(source.slice)}`,
    source.time === undefined ? "" : `&t=${source.time}`,
    source.schedule === undefined || source.schedule.length === 0
      ? ""
      : `&schedule=${scheduleText(source.schedule)}`,
    source.daily === undefined ? "" : `&daily=${dailyText(source.daily)}`,
    source.targets === undefined || source.targets.length === 0
      ? ""
      : `&targets=${targetsText(source.targets)}`,
    source.compare === undefined ? "" : `&compare=${encodeURIComponent(source.compare)}`,
    source.probes === undefined || source.probes.length === 0
      ? ""
      : `&probes=${probesText(source.probes)}`,
  ].join("");
}

/** `key:number` pairs, sorted by key, as the address bar and the simulator's
 * API both take them: `length:12,spans:3`. */
export function pairsText(pairs: Readonly<Record<string, number>> | undefined): string {
  return Object.entries(pairs ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, number]) => `${encodeURIComponent(key)}:${number}`)
    .join(",");
}

/** The changes a scenario's scene asks the simulator for: another of its
 * layouts (`layout=`), its greenhouse's dimensions (`envelope=`), its
 * openings (`open=`) and its equipment's levels (`set=`), or nothing. The
 * address bar writes them the same way. */
export function changesQuery(
  source: {
    layout?: string;
    envelope?: Readonly<Record<string, number>>;
    openings?: Readonly<Record<string, number>>;
    levels?: Readonly<Record<string, number>>;
  },
  separator: "?" | "&",
): string {
  const parts = [
    ["layout", layoutText(source.layout ?? "")],
    ["envelope", pairsText(source.envelope)],
    ["open", pairsText(source.openings)],
    ["set", pairsText(source.levels)],
  ].filter(([, text]) => text !== "");
  return parts.length === 0
    ? ""
    : `${separator}${parts.map(([name, text]) => `${name}=${text}`).join("&")}`;
}

/** Commands as the address bar and the simulator's API both write them:
 * `60:fan:1,300:heater:0`, in the order given. */
export function scheduleText(commands: readonly ScheduledCommand[] | undefined): string {
  return (commands ?? [])
    .map(({ timeS, actuatorId, level }) => `${timeS}:${encodeURIComponent(actuatorId)}:${level}`)
    .join(",");
}

/** The commands an address sets, or null when it sets none or says nothing
 * readable. The simulator checks them itself. */
export function scheduleFrom(value: string | null): ScheduledCommand[] | null {
  if (!value) {
    return null;
  }
  const commands: ScheduledCommand[] = [];
  for (const command of value.split(",")) {
    const [time, actuatorId, level] = command.split(":");
    const timeS = Number(time);
    const shown = Number(level);
    if (!actuatorId || level === undefined || !Number.isFinite(timeS) || !Number.isFinite(shown)) {
      return null;
    }
    commands.push({ timeS, actuatorId: decodeURIComponent(actuatorId), level: shown });
  }
  return commands;
}

/** Crop actions as the address bar and the simulator's API both write them
 * (P13.8): `86400:p30:lower_stem:1,172800:p30:harvest_truss:p30_t03`, in
 * the order given. */
export function cropText(actions: readonly CropCommand[] | undefined): string {
  return (actions ?? [])
    .map(
      ({ timeS, plantId, kind, target }) =>
        `${timeS}:${encodeURIComponent(plantId)}:${kind}:${encodeURIComponent(target)}`,
    )
    .join(",");
}

/** The crop actions an address asks for, or null when it asks for none or
 * says nothing readable: `value` as the address's parameters read it,
 * decoded once already. The simulator checks them itself. */
export function cropFrom(value: string | null): CropCommand[] | null {
  if (!value) {
    return null;
  }
  const actions: CropCommand[] = [];
  for (const action of value.split(",")) {
    const [time, plantId, kind, ...rest] = action.split(":");
    const timeS = Number(time);
    if (!plantId || !kind || rest.length === 0 || !Number.isFinite(timeS)) {
      return null;
    }
    actions.push({ timeS, plantId, kind, target: rest.join(":") });
  }
  return actions;
}

/** Target changes as the address bar and the simulator's API both write
 * them: `25200:heating_day:24`, in the order given (#274). */
export function targetsText(changes: readonly TargetChange[] | undefined): string {
  return (changes ?? [])
    .map(({ timeS, target, valueC }) => `${timeS}:${encodeURIComponent(target)}:${valueC}`)
    .join(",");
}

/** The target changes an address makes, or null when it makes none or says
 * nothing readable. The simulator checks them itself. */
export function targetsFrom(value: string | null): TargetChange[] | null {
  const read = scheduleFrom(value);
  return read === null
    ? null
    : read.map(({ timeS, actuatorId, level }) => ({ timeS, target: actuatorId, valueC: level }));
}

/** How the address and the simulator's API ask for a run without daily
 * commands, its scenario's own too. */
export const NO_DAILY_COMMANDS = "none";

/** A run's daily commands as the address and the API write them: none as
 * `none`, so that a run without them is told from one with its scenario's. */
export function dailyText(commands: readonly ScheduledCommand[]): string {
  return commands.length === 0 ? NO_DAILY_COMMANDS : scheduleText(commands);
}

/** The daily commands an address gives a run, none if it says `none`, or
 * null if it gives none or nothing readable: then its scenario's own. */
function dailyFrom(value: string | null): ScheduledCommand[] | null {
  return value === NO_DAILY_COMMANDS ? [] : scheduleFrom(value);
}

/** A cloud cover the address overrides the weather's with, from 0 to 100 %,
 * or null when it says none or nothing readable. */
function cloudsFrom(value: string | null): number | null {
  const clouds = Number(value ?? "");
  return value !== null && value !== "" && clouds >= 0 && clouds <= MOST_CLOUDS_PCT ? clouds : null;
}

/** A wind direction the address overrides the weather's with, a bearing
 * from 0 to 360°, or null when it says none or nothing readable. */
function windFrom(value: string | null): number | null {
  const wind = Number(value ?? "");
  return value !== null && value !== "" && wind >= 0 && wind < FULL_TURN_DEG ? wind : null;
}

/** The weather the simulator is asked for: another by name, or its own, its
 * clouds overridden as `@80` asks, and its wind's direction as `~90` does,
 * for QA. */
export function apiWeather(
  weather: string | undefined,
  clouds: number | undefined,
  wind?: number,
): string | undefined {
  if (clouds === undefined && wind === undefined) {
    return weather;
  }
  const clouded = clouds === undefined ? "" : `${CLOUDS_MARK}${clouds}`;
  const winded = wind === undefined ? "" : `${WIND_MARK}${wind}`;
  return `${weather ?? DEFAULT_WEATHER}${clouded}${winded}`;
}

/** The moment an address asks for, in seconds from 0, or null. */
function timeFrom(value: string | null): number | null {
  const time = Number(value ?? "");
  return value !== null && value !== "" && Number.isFinite(time) && time >= 0 ? time : null;
}

/** The pairs an address sets, or null when it sets none or says nothing
 * readable. The simulator checks the numbers themselves. */
export function pairsFrom(value: string | null): Record<string, number> | null {
  if (!value) {
    return null;
  }
  const pairs: Record<string, number> = {};
  for (const pair of value.split(",")) {
    const [key, text] = pair.split(":");
    const number = Number(text);
    if (!key || text === undefined || Number.isNaN(number)) {
      return null;
    }
    pairs[key] = number;
  }
  return pairs;
}

/** A camera pose as the address writes it: its position, then the point it
 * looks at, `x:y:z,x:y:z`. Probes are written the same way. */
export function cameraFrom(text: string | null): CameraPose | undefined {
  const points = probesFrom(text);
  if (points === undefined || points.length !== 2) {
    return undefined;
  }
  const [position, target] = points as [CameraPose["position"], CameraPose["target"]];
  return { position, target };
}

export function cameraText(pose: CameraPose): string {
  return probesText([pose.position, pose.target]);
}
