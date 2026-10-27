import { contractReader } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import type { Point3 } from "../world";
import { OBSERVATIONS_SCHEMA } from "./generated/observationsSchema";
import type {
  CameraPose,
  Observation,
  SensorFreshness,
  SensorObservations,
} from "./generated/observationsTypes";
import { TRUTH_SCHEMA } from "./generated/truthSchema";
import type { SensorTruth, SensorTruths } from "./generated/truthTypes";

// A sensor's freshness, a camera's pose and what a sensor truly sampled, as
// the simulator publishes them.
export type { CameraPose, SensorFreshness, SensorTruth };

/** An observation as the viewer reads it: what a sensor reported, when it
 * took it and when it was delivered, and what is known of the reading, such
 * as "CLIPPED"; absent if nothing. */
export type SensorObservation = Pick<
  Observation,
  "sensor_id" | "observation_type" | "timestamp" | "delivered_at" | "value" | "quality"
>;

/** A frame a camera took, as the viewer reads it from the log: when, from
 * where, turned how, with what intrinsics, and what it holds; not its
 * pixels. */
export interface CameraFrame {
  frame_id: string;
  sensor_id: string;
  timestamp: string;
  pose: CameraPose;
  intrinsics: { width: number; height: number; fx: number; fy: number };
  modalities: string[];
}

/** A run's observation log up to a moment, what its sensors observed, each
 * one's freshness and its cameras' frames; and, in QA mode, what they truly
 * sampled, none otherwise. */
export interface SensorReadings {
  runId: string;
  /** When the run started, as an instant. */
  start: string;
  observations: SensorObservation[];
  freshness: SensorFreshness[];
  frames: CameraFrame[];
  truths: SensorTruth[];
}

export type SensorReadingsState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; readings: SensorReadings };

/** The run's changes, as the climate is asked for with them. */
export type RunChanges = RunParts & {
  /** Observations as clean sensors would have made them, for QA. */
  clean?: boolean | undefined;
};

/** Where a run's sensors' observations, or their truth, are published,
 * asked for as the climate is, up to the moment drawn. */
export function sensorsUrl(
  scenarioId: string,
  what: "observations" | "truth",
  run: RunChanges,
): string {
  return scenarioUrl(scenarioId, `climate/${what}`, [
    ...runParameters(run, [
      "layout",
      "levels",
      "openings",
      "schedule",
      "daily",
      "targets",
      "crop",
      "time",
    ]),
    ...(what === "observations" && run.clean === true ? ["clean=1"] : []),
    ...runParameters(run, ["weather"]),
  ]);
}

const UNEXPECTED = "the readings are not what the viewer expects";

/** A run's observation log, checked rather than trusted. */
export const readObservations = contractReader<SensorObservations>(OBSERVATIONS_SCHEMA, UNEXPECTED);
const readTruths = contractReader<SensorTruths>(TRUTH_SCHEMA, UNEXPECTED);

/** A run's sensors' logs, as the viewer asks for them: a scenario's, under
 * a run's changes, with what its sensors truly sampled only if `truth` is
 * asked for, in QA mode (P09.6). */
export interface SensorsRequest {
  scenarioId: string;
  run: RunChanges;
  truth: boolean;
}

/** What names a request for a run's sensors' logs: the observations'
 * address, which holds every change it asks for, and whether the truth is
 * asked for beside them. */
export function sensorsKey({ scenarioId, run, truth }: SensorsRequest): string {
  return `${sensorsUrl(scenarioId, "observations", run)}${truth ? " with its truth" : ""}`;
}

/** Fetches a run's sensors' observations, and their truth only if asked
 * for; every failure becomes a state. */
export async function loadSensorReadings(
  { scenarioId, run, truth: withTruth }: SensorsRequest,
  fetchFn: typeof fetch = fetch,
): Promise<SensorReadingsState> {
  try {
    const [observed, truth] = await Promise.all([
      fetchFn(sensorsUrl(scenarioId, "observations", run)),
      withTruth ? fetchFn(sensorsUrl(scenarioId, "truth", run)) : null,
    ]);
    if (!observed.ok || (truth !== null && !truth.ok)) {
      const status = observed.ok ? truth?.status : observed.status;
      return { status: "unavailable", reason: `the simulator API answered ${status}` };
    }
    const observations = readObservations(await observed.json());
    const truths = truth === null ? [] : readTruths(await truth.json()).sensors;
    return {
      status: "loaded",
      readings: {
        runId: observations.run_id,
        start: observations.start,
        observations: observations.observations,
        freshness: observations.freshness,
        frames: observations.frames,
        truths,
      },
    };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

/** Seconds from a run's start to an instant, as the simulator stamps both. */
export function secondsInto(start: string, instant: string): number {
  return (Date.parse(instant) - Date.parse(start)) / MS_PER_SECOND;
}

/** A sensor's freshness at the moment drawn, if the log says. */
export function freshnessOf(
  readings: SensorReadings,
  sensorId: string,
): SensorFreshness | undefined {
  return readings.freshness.find((f) => f.sensor_id === sensorId);
}

/** Where a pose's camera looks, in its greenhouse's frame: the unit vector
 * its quaternion turns the camera's x axis into. */
export function lookingAlong({ qw, qx, qy, qz }: CameraPose): Point3 {
  return {
    x: 1 - 2 * (qy * qy + qz * qz),
    y: 2 * (qx * qy + qw * qz),
    z: 2 * (qx * qz - qw * qy),
  };
}

/** A camera's frames up to the moment drawn, in the order taken. */
export function framesOf(readings: SensorReadings, cameraId: string): CameraFrame[] {
  return readings.frames.filter((frame) => frame.sensor_id === cameraId);
}

/** A sensor's latest reading delivered by the moment drawn, if any. */
export function latestReading(
  readings: SensorReadings,
  sensorId: string,
): SensorObservation | undefined {
  return readings.observations.filter((o) => o.sensor_id === sensorId).at(-1);
}

/** What a sensor truly sampled at its latest moment, and that moment. */
export function latestTruth(
  readings: SensorReadings,
  sensorId: string,
): { timeS: number; value: number | null; unit: string } | undefined {
  const truth = readings.truths.find((t) => t.sensor_id === sensorId);
  const last = truth === undefined ? -1 : truth.times_s.length - 1;
  if (truth === undefined || last < 0) {
    return undefined;
  }
  return { timeS: truth.times_s[last] ?? 0, value: truth.values[last] ?? null, unit: truth.unit };
}

/** A sensor's readings and truth through the run so far, as points in
 * seconds from its start. */
export function sensorSeries(
  readings: SensorReadings,
  sensorId: string,
): { observed: [number, number][]; truth: [number, number][] } {
  const start = Date.parse(readings.start);
  const observed = readings.observations
    .filter((o) => o.sensor_id === sensorId)
    .map((o): [number, number] => [(Date.parse(o.timestamp) - start) / MS_PER_SECOND, o.value]);
  const known = readings.truths.find((t) => t.sensor_id === sensorId);
  const truth: [number, number][] = [];
  known?.times_s.forEach((time, index) => {
    const value = known.values[index];
    if (value !== null && value !== undefined) {
      truth.push([time, value]);
    }
  });
  return { observed, truth };
}

const MS_PER_SECOND = 1000;
