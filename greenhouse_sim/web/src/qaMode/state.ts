import { describeTime } from "../fields/ClimateTime";
import { formatValue } from "../readouts";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import {
  type CameraFrame,
  isFrame,
  isFreshness,
  type SensorFreshness,
  secondsInto,
} from "../sensors/readings";
import { PERCENT } from "../units";

/** A command a run gave its equipment, a door or a vent, at a moment. */
export interface GivenCommand {
  timeS: number;
  actuatorId: string;
  level: number;
}

/** Where a camera stands with its frames: how many it has taken since the
 * run's start, and its latest. */
export interface CameraState {
  sensorId: string;
  frames: number;
  latest: CameraFrame | null;
}

/** What each process of a scenario's run holds at a moment, as the
 * simulator says (`GET /api/scenarios/{id}/climate/state`, P09.6). */
export interface RunState {
  runId: string;
  /** When the run started, and the instant it is, as the simulator stamps
   * them; the moment, in seconds from the start, and its day. */
  start: string;
  at: string;
  timeS: number;
  day: number;
  /** The house's air, if the run has a climate. */
  houseAir: { temperatureC: number; humidityPct: number; co2Ppm: number } | null;
  cropModel: string;
  plants: number;
  daysLived: number;
  /** Each piece of equipment's level, and how far each door and vent
   * stands open, by identifier. */
  levels: Record<string, number>;
  commandsGiven: number;
  latestCommands: GivenCommand[];
  sensors: SensorFreshness[];
  cameras: CameraState[];
}

export type RunStateState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; state: RunState };

/** Where what each process of a scenario's run holds at its moment is
 * published, the run asked for as the climate is. */
export function runStateUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/state", runParameters(run));
}

const UNEXPECTED = "the run's state is not what the viewer expects";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumbers(value: unknown): value is Record<string, number> {
  return isObject(value) && Object.values(value).every((entry) => typeof entry === "number");
}

function commandFrom(value: unknown): GivenCommand {
  if (
    !isObject(value) ||
    typeof value.time_s !== "number" ||
    typeof value.actuator_id !== "string" ||
    typeof value.level !== "number"
  ) {
    throw new Error(UNEXPECTED);
  }
  return { timeS: value.time_s, actuatorId: value.actuator_id, level: value.level };
}

function cameraFrom(value: unknown): CameraState {
  if (
    !isObject(value) ||
    typeof value.sensor_id !== "string" ||
    typeof value.frames !== "number" ||
    !(value.latest === null || isFrame(value.latest))
  ) {
    throw new Error(UNEXPECTED);
  }
  return { sensorId: value.sensor_id, frames: value.frames, latest: value.latest };
}

function houseAirFrom(value: unknown): RunState["houseAir"] {
  if (value === null) {
    return null;
  }
  if (
    !isObject(value) ||
    typeof value.temperature_c !== "number" ||
    typeof value.humidity_pct !== "number" ||
    typeof value.co2_ppm !== "number"
  ) {
    throw new Error(UNEXPECTED);
  }
  return {
    temperatureC: value.temperature_c,
    humidityPct: value.humidity_pct,
    co2Ppm: value.co2_ppm,
  };
}

/** A run's state, checked rather than trusted. */
export function parseRunState(body: unknown): RunState {
  if (
    !isObject(body) ||
    typeof body.run_id !== "string" ||
    typeof body.start !== "string" ||
    typeof body.at !== "string" ||
    typeof body.time_s !== "number" ||
    typeof body.day !== "number" ||
    typeof body.crop_model !== "string" ||
    typeof body.plants !== "number" ||
    typeof body.days_lived !== "number" ||
    !isNumbers(body.levels) ||
    typeof body.commands_given !== "number" ||
    !Array.isArray(body.latest_commands) ||
    !Array.isArray(body.sensors) ||
    !body.sensors.every(isFreshness) ||
    !Array.isArray(body.cameras)
  ) {
    throw new Error(UNEXPECTED);
  }
  return {
    runId: body.run_id,
    start: body.start,
    at: body.at,
    timeS: body.time_s,
    day: body.day,
    houseAir: houseAirFrom(body.house_air),
    cropModel: body.crop_model,
    plants: body.plants,
    daysLived: body.days_lived,
    levels: body.levels,
    commandsGiven: body.commands_given,
    latestCommands: body.latest_commands.map(commandFrom),
    sensors: body.sensors,
    cameras: body.cameras.map(cameraFrom),
  };
}

/** Fetches a run's state from its `runStateUrl`; every failure becomes
 * `unavailable`. */
export async function loadRunState(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<RunStateState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", state: parseRunState(await response.json()) };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

/** A level, or how far a door stands open, in %. */
function percent(level: number): string {
  return `${Math.round(level * PERCENT)}%`;
}

/** An instant as the simulator stamps it, to the minute, in UTC. */
function instant(stamp: string): string {
  return `${stamp.slice(0, "2026-03-01T12:00".length).replace("T", " ")} UTC`;
}

/** What each process holds, in words, a line for each. */
export function describeRunState(state: RunState): {
  clock: string;
  houseAir: string;
  crop: string;
  levels: string;
  commands: string[];
  sensors: { id: string; text: string; stale: boolean }[];
  cameras: { id: string; text: string }[];
} {
  const air = state.houseAir;
  const lastDay = state.daysLived - 1;
  return {
    clock: `${describeTime(state.timeS)} (${instant(state.at)}), run ${state.runId}`,
    houseAir:
      air === null
        ? "none: without equipment the run has no climate"
        : `${formatValue(air.temperatureC)} °C, ${formatValue(air.humidityPct)}%, ${formatValue(air.co2Ppm)} ppm`,
    crop: `${state.plants} plants, ${state.cropModel === "organ" ? "organ by organ" : "the simple daily model"}; ${
      lastDay < 0 ? "no day lived yet" : `last plant day ${lastDay}`
    }`,
    levels:
      Object.keys(state.levels).length === 0
        ? "none"
        : Object.entries(state.levels)
            .map(([id, level]) => `${id} ${percent(level)}`)
            .join(", "),
    commands: state.latestCommands.map(
      (command) =>
        `${describeTime(command.timeS)}: ${command.actuatorId} ${percent(command.level)}`,
    ),
    sensors: state.sensors.map((sensor) => ({
      id: sensor.sensor_id,
      stale: sensor.state === "stale",
      text: `${sensor.sensor_id}: ${sensor.state}${
        sensor.latest_at === null
          ? ""
          : `, latest ${describeTime(secondsInto(state.start, sensor.latest_at))}`
      }`,
    })),
    cameras: state.cameras.map((camera) => ({
      id: camera.sensorId,
      text: `${camera.sensorId}: ${camera.frames} frames${
        camera.latest === null
          ? ""
          : `, latest ${describeTime(secondsInto(state.start, camera.latest.timestamp))}`
      }`,
    })),
  };
}
