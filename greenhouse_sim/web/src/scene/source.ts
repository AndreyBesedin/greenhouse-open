import type { CameraPose } from "../camera";
import { type FieldView, fieldViewFrom, type Slice, sliceFrom, sliceText } from "../fields/display";
import { probesFrom, probesText } from "../fields/probes";
import {
  actionFrom,
  actionsQuery,
  FIRST_LAB_RUN,
  type LabRun,
  labRunQuery,
  PLANT_LAB_LAST_DAY,
  PLANT_LAB_SEED,
} from "../plants/lab";
import { stressPlants, stressScene } from "../qa/stressScene";
import type { Point3 } from "../world";
import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

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
      /** Another of its fields, compared with the drawn one at the probes. */
      compare?: string;
      /** Points the drawn field is read at. */
      probes?: Point3[];
      /** Whether the boundaries a CFD solver is given are drawn over it. */
      cfdBoundaries?: true;
      /** Where the camera starts, rather than the default preset: for a part
       * of a big greenhouse no preset frames. */
      camera?: CameraPose;
      envelope?: Readonly<Record<string, number>>;
      openings?: Readonly<Record<string, number>>;
      levels?: Readonly<Record<string, number>>;
    }
  | { kind: "live"; scenarioId: string };

/** A command to a piece of equipment at a moment of a climate run. */
export interface ScheduledCommand {
  timeS: number;
  actuatorId: string;
  level: number;
}

export type SceneState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "rejected"; problems: string[] }
  | { status: "loaded"; snapshot: SceneSnapshot };

const EXAMPLE_SCENE_URL = "/scenes/example.json";
// The simulator writes it (`tests/test_scene_schema.py --update`).
export const FIXTURE_GALLERY_URL = "/scenes/qa-fixtures.json";
export const PLANT_LAB_SCENE_URL = "/api/plants/scene";
// The address's `cfd=` when a scenario's CFD boundaries are drawn.
const CFD_BOUNDARIES = "boundaries";

export function sourceFromSearch(search: string): SceneSource {
  const parameters = new URLSearchParams(search);
  const liveId = parameters.get("live");
  if (liveId) {
    return { kind: "live", scenarioId: liveId };
  }
  const scenarioId = parameters.get("scenario");
  if (scenarioId) {
    const layout = parameters.get("layout");
    const envelope = pairsFrom(parameters.get("envelope"));
    const openings = pairsFrom(parameters.get("open"));
    const levels = pairsFrom(parameters.get("set"));
    const field = parameters.get("field");
    const fieldView = fieldViewFrom(parameters.get("fieldView"));
    const slice = sliceFrom(parameters.get("slice"));
    const compare = parameters.get("compare");
    const time = timeFrom(parameters.get("t"));
    const schedule = scheduleFrom(parameters.get("schedule"));
    const probes = probesFrom(parameters.get("probes"));
    const camera = cameraFrom(parameters.get("camera"));
    return {
      kind: "scenario",
      scenarioId,
      ...(layout ? { layout } : {}),
      ...(field ? { field } : {}),
      ...(field && fieldView ? { fieldView } : {}),
      ...(field && slice ? { slice } : {}),
      ...(field && time !== null ? { time } : {}),
      ...(field && schedule !== null ? { schedule } : {}),
      ...(field && compare && compare !== field ? { compare } : {}),
      ...(field && probes ? { probes } : {}),
      ...(parameters.get("cfd") === CFD_BOUNDARIES ? { cfdBoundaries: true as const } : {}),
      ...(camera === undefined ? {} : { camera }),
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
      return `?scenario=${encodeURIComponent(source.scenarioId)}${changesQuery(source, "&")}${fieldQuery(source)}${source.cfdBoundaries ? `&cfd=${CFD_BOUNDARIES}` : ""}${source.camera === undefined ? "" : `&camera=${cameraText(source.camera)}`}`;
    case "live":
      return `?live=${encodeURIComponent(source.scenarioId)}`;
  }
}

/** How a scenario's field is drawn, compared and probed, as the address bar
 * writes it. */
function fieldQuery(source: {
  field?: string;
  fieldView?: FieldView;
  slice?: Slice;
  time?: number;
  schedule?: ScheduledCommand[];
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
    ["layout", encodeURIComponent(source.layout ?? "")],
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

/** A scenario's equipment's levels at the moment of its climate run drawn:
 * those set from the start, then its commands up to that moment, in time
 * order, the later winning at a moment. */
export function levelsAt(source: {
  levels?: Readonly<Record<string, number>>;
  schedule?: readonly ScheduledCommand[];
  time?: number;
}): Record<string, number> {
  const now = source.time ?? 0;
  const levels: Record<string, number> = { ...(source.levels ?? {}) };
  const applied = (source.schedule ?? [])
    .map((command, order) => ({ command, order }))
    .filter(({ command }) => command.timeS <= now)
    .sort((a, b) => a.command.timeS - b.command.timeS || a.order - b.order);
  for (const { command } of applied) {
    levels[command.actuatorId] = command.level;
  }
  return levels;
}

/** The schedule with an override at a moment: each actuator's command at
 * that moment replaced by the level it is set to, kept in time order. */
export function withOverride(
  schedule: readonly ScheduledCommand[],
  timeS: number,
  levels: Readonly<Record<string, number>>,
): ScheduledCommand[] {
  const kept = schedule.filter(
    (command) => !(command.timeS === timeS && command.actuatorId in levels),
  );
  const added = Object.entries(levels).map(([actuatorId, level]) => ({ timeS, actuatorId, level }));
  return [...kept, ...added]
    .map((command, order) => ({ command, order }))
    .sort((a, b) => a.command.timeS - b.command.timeS || a.order - b.order)
    .map(({ command }) => command);
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

function sceneUrl(source: SceneSource): string | null {
  switch (source.kind) {
    case "reference":
    case "stress":
    case "live":
      // A stress scene is built here, and a live scene streams in (see useLiveScene).
      return null;
    case "example":
      return EXAMPLE_SCENE_URL;
    case "fixtures":
      return FIXTURE_GALLERY_URL;
    case "plants":
      return `${PLANT_LAB_SCENE_URL}?${labRunQuery(source)}`;
    case "scenario":
      // Its equipment as it stands at the moment of its climate run drawn.
      return `/api/scenarios/${encodeURIComponent(source.scenarioId)}/scene${changesQuery({ ...source, levels: levelsAt(source) }, "?")}`;
  }
}

/** Fetches and checks the chosen scene; every failure becomes a state to show. */
export async function loadScene(
  source: SceneSource,
  fetchFn: typeof fetch = fetch,
): Promise<SceneState> {
  if (source.kind === "stress") {
    // The viewer builds it, so it needs no check.
    return { status: "loaded", snapshot: stressScene(source.plants) };
  }
  const url = sceneUrl(source);
  return url === null ? { status: "none" } : fetchScene(url, fetchFn);
}

/** Why a scene was refused: the simulator's own reason, where it gives one. */
async function refusal(url: string, response: Response): Promise<string> {
  const answered = `${url} answered ${response.status}`;
  try {
    const body: unknown = await response.json();
    const error =
      typeof body === "object" && body !== null ? (body as Record<string, unknown>).error : null;
    return typeof error === "string" ? `${answered}: ${error}` : answered;
  } catch {
    return answered;
  }
}

/** Fetches and checks the scene at `url`; every failure becomes a state to show. */
export async function fetchScene(url: string, fetchFn: typeof fetch = fetch): Promise<SceneState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: await refusal(url, response) };
    }
    const check = checkScene(await response.json());
    return check.ok
      ? { status: "loaded", snapshot: check.snapshot }
      : { status: "rejected", problems: check.problems };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}

/** The scenario on show with another of its layouts keeps how its air is
 * drawn, probed and compared, so that the two layouts' air can be compared;
 * any other choice starts afresh. */
export function withItsAir(shown: SceneSource, chosen: SceneSource): SceneSource {
  if (
    shown.kind !== "scenario" ||
    chosen.kind !== "scenario" ||
    shown.scenarioId !== chosen.scenarioId
  ) {
    return chosen;
  }
  const { field, fieldView, slice, compare, probes, cfdBoundaries } = shown;
  return {
    ...chosen,
    ...(field === undefined ? {} : { field }),
    ...(fieldView === undefined ? {} : { fieldView }),
    ...(slice === undefined ? {} : { slice }),
    ...(compare === undefined ? {} : { compare }),
    ...(probes === undefined ? {} : { probes }),
    ...(cfdBoundaries === undefined ? {} : { cfdBoundaries }),
  };
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
