import { pairsText, type ScheduledCommand, scheduleText } from "../scene/source";
import type { Point3 } from "../world";

/** An observation as the simulator sends it: what a sensor reported, when it
 * took it and when it was delivered. */
export interface SensorObservation {
  sensor_id: string;
  observation_type: string;
  timestamp: string;
  delivered_at?: string;
  value: number;
  /** What is known of the reading, such as "CLIPPED"; absent if nothing. */
  quality?: string[];
}

/** Whether a sensor's latest reading due by the moment drawn has come: the
 * moments its due and latest readings were taken, as instants. */
export interface SensorFreshness {
  sensor_id: string;
  due_at: string | null;
  latest_at: string | null;
  stale: boolean;
}

/** A frame a camera took, as the log records it: when, from where, looking
 * where, with what intrinsics, and what it holds; not its pixels. */
export interface CameraFrame {
  frame_id: string;
  sensor_id: string;
  timestamp: string;
  position: Point3;
  target: Point3;
  intrinsics: { width: number; height: number; fx: number; fy: number };
  modalities: string[];
}

/** What a sensor truly sampled at each of its moments, in seconds from the
 * run's start: for QA only. */
export interface SensorTruth {
  sensor_id: string;
  observation_type: string;
  unit: string;
  times_s: number[];
  values: (number | null)[];
}

/** A run's observation log up to a moment, what its sensors observed, each
 * one's freshness and its cameras' frames; and, for QA, what they truly
 * sampled. */
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
export interface RunChanges {
  layout?: string | undefined;
  levels?: Readonly<Record<string, number>> | undefined;
  openings?: Readonly<Record<string, number>> | undefined;
  schedule?: readonly ScheduledCommand[] | undefined;
  time?: number | undefined;
  /** Observations as clean sensors would have made them, for QA. */
  clean?: boolean | undefined;
}

/** Where a run's sensors' observations, or their truth, are published,
 * asked for as the climate is, up to the moment drawn. */
export function sensorsUrl(
  scenarioId: string,
  what: "observations" | "truth",
  run: RunChanges,
): string {
  const parts = [
    ...(run.layout === undefined ? [] : [`layout=${encodeURIComponent(run.layout)}`]),
    ...(pairsText(run.levels) === "" ? [] : [`set=${pairsText(run.levels)}`]),
    ...(pairsText(run.openings) === "" ? [] : [`open=${pairsText(run.openings)}`]),
    ...(scheduleText(run.schedule) === "" ? [] : [`schedule=${scheduleText(run.schedule)}`]),
    ...(run.time === undefined || run.time === 0 ? [] : [`t=${run.time}`]),
    ...(what === "observations" && run.clean === true ? ["clean=1"] : []),
  ];
  const query = parts.length === 0 ? "" : `?${parts.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/${what}${query}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isObservation(value: unknown): value is SensorObservation {
  return (
    isObject(value) &&
    typeof value.sensor_id === "string" &&
    typeof value.observation_type === "string" &&
    typeof value.timestamp === "string" &&
    typeof value.value === "number"
  );
}

function isFreshness(value: unknown): value is SensorFreshness {
  return (
    isObject(value) &&
    typeof value.sensor_id === "string" &&
    (value.due_at === null || typeof value.due_at === "string") &&
    (value.latest_at === null || typeof value.latest_at === "string") &&
    typeof value.stale === "boolean"
  );
}

function isPoint(value: unknown): value is Point3 {
  return (
    isObject(value) &&
    typeof value.x === "number" &&
    typeof value.y === "number" &&
    typeof value.z === "number"
  );
}

function isFrame(value: unknown): value is CameraFrame {
  return (
    isObject(value) &&
    typeof value.frame_id === "string" &&
    typeof value.sensor_id === "string" &&
    typeof value.timestamp === "string" &&
    isPoint(value.position) &&
    isPoint(value.target) &&
    isObject(value.intrinsics) &&
    typeof value.intrinsics.width === "number" &&
    typeof value.intrinsics.height === "number" &&
    Array.isArray(value.modalities)
  );
}

function isTruth(value: unknown): value is SensorTruth {
  return (
    isObject(value) &&
    typeof value.sensor_id === "string" &&
    typeof value.unit === "string" &&
    Array.isArray(value.times_s) &&
    Array.isArray(value.values)
  );
}

/** Fetches a run's sensors' observations and their truth; every failure
 * becomes a state. */
export async function loadSensorReadings(
  scenarioId: string,
  run: RunChanges,
  fetchFn: typeof fetch = fetch,
): Promise<SensorReadingsState> {
  try {
    const [observed, truth] = await Promise.all(
      (["observations", "truth"] as const).map((what) =>
        fetchFn(sensorsUrl(scenarioId, what, run)),
      ),
    );
    if (observed === undefined || truth === undefined || !observed.ok || !truth.ok) {
      const status = observed?.ok ? truth?.status : observed?.status;
      return { status: "unavailable", reason: `the simulator API answered ${status}` };
    }
    const observations: unknown = await observed.json();
    const truths: unknown = await truth.json();
    if (
      !isObject(observations) ||
      !Array.isArray(observations.observations) ||
      !observations.observations.every(isObservation) ||
      !Array.isArray(observations.freshness) ||
      !observations.freshness.every(isFreshness) ||
      !Array.isArray(observations.frames) ||
      !observations.frames.every(isFrame) ||
      !isObject(truths) ||
      !Array.isArray(truths.sensors) ||
      !truths.sensors.every(isTruth)
    ) {
      return { status: "unavailable", reason: "the readings are not what the viewer expects" };
    }
    return {
      status: "loaded",
      readings: {
        runId: typeof observations.run_id === "string" ? observations.run_id : "",
        start: typeof observations.start === "string" ? observations.start : "",
        observations: observations.observations,
        freshness: observations.freshness,
        frames: observations.frames,
        truths: truths.sensors,
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
