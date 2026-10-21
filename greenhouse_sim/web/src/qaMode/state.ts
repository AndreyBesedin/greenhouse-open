import { describeTime } from "../fields/ClimateTime";
import { contractReader, loadJson } from "../loadJson";
import { formatValue } from "../readouts";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { type CameraFrame, type SensorFreshness, secondsInto } from "../sensors/readings";
import { PERCENT } from "../units";
import { RUN_STATE_SCHEMA } from "./generated/runStateSchema";
import type { RunState as ServedState } from "./generated/runStateTypes";

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

const readState = contractReader<ServedState>(
  RUN_STATE_SCHEMA,
  "the run's state is not what the viewer expects",
);

/** A run's state, checked rather than trusted. */
export function parseRunState(body: unknown): RunState {
  const served = readState(body);
  const air = served.house_air;
  return {
    runId: served.run_id,
    start: served.start,
    at: served.at,
    timeS: served.time_s,
    day: served.day,
    houseAir:
      air === null
        ? null
        : { temperatureC: air.temperature_c, humidityPct: air.humidity_pct, co2Ppm: air.co2_ppm },
    cropModel: served.crop_model,
    plants: served.plants,
    daysLived: served.days_lived,
    levels: served.levels,
    commandsGiven: served.commands_given,
    latestCommands: served.latest_commands.map((command) => ({
      timeS: command.time_s,
      actuatorId: command.actuator_id,
      level: command.level,
    })),
    sensors: served.sensors,
    cameras: served.cameras.map((camera) => ({
      sensorId: camera.sensor_id,
      frames: camera.frames,
      latest: camera.latest,
    })),
  };
}

/** Fetches a run's state from its `runStateUrl`; every failure becomes
 * `unavailable`. */
export async function loadRunState(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<RunStateState> {
  const answer = await loadJson(url, parseRunState, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", state: answer.value } : answer;
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
