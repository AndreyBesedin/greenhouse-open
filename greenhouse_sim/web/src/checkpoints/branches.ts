import { houseAirUrl, parseHouseAir } from "../fields/HouseAir";
import { type CropPlant, cropPlantUrl, parseCropPlant } from "../plants/crop";
import { DEFAULT_WEATHER } from "../scenarios";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { RunParts } from "../scene/run";
import { readObservations, secondsInto, sensorsUrl } from "../sensors/readings";
import type { CheckpointSummary } from "./checkpoints";

/** A checkpoint's run carried on unchanged from its moment, at the moment
 * drawn: branch A of a comparison (P09.5). */
export function checkpointRun(checkpoint: CheckpointSummary, time: number): RunParts {
  return {
    ...(checkpoint.layout === "default" ? {} : { layout: checkpoint.layout }),
    ...(Object.keys(checkpoint.levels).length === 0 ? {} : { levels: checkpoint.levels }),
    ...(Object.keys(checkpoint.openings).length === 0 ? {} : { openings: checkpoint.openings }),
    ...(checkpoint.commands.length === 0 ? {} : { schedule: checkpoint.commands }),
    ...(checkpoint.daily === null ? {} : { daily: checkpoint.daily }),
    ...(checkpoint.targets.length === 0 ? {} : { targets: checkpoint.targets }),
    ...(checkpoint.weather === DEFAULT_WEATHER ? {} : { weather: checkpoint.weather }),
    time,
  };
}

/** Two branches' values at the same moments, in seconds from the run's
 * start, or days. */
export interface TwoSeries {
  at: number[];
  a: number[];
  b: number[];
}

/** Two branches compared at the moment drawn: the house's air through its
 * day; a sensor's readings through it, if one is compared; and a plant's
 * days since the checkpoint, with how far it has developed, if the
 * scenario grows its crop organ by organ. */
export interface Comparison {
  house: TwoSeries;
  sensor: { sensorId: string; readings: TwoSeries } | null;
  plant: {
    plantId: string;
    temperature: TwoSeries;
    light: TwoSeries;
    thermalTime: { a: number; b: number };
  } | null;
}

export type ComparisonState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; comparison: Comparison };

/** What a comparison asks for: a scenario's branches A and B, from a
 * checkpoint's day, a sensor and a plant to compare, if any. */
export interface ComparisonRequest {
  scenarioId: string;
  a: RunParts;
  b: RunParts;
  fromDay: number;
  sensorId: string | null;
  plantId: string | null;
}

/** What names a comparison: every address it asks for. */
export function comparisonKey(request: ComparisonRequest): string {
  return urls(request).join(" ");
}

function urls({ scenarioId, a, b, sensorId, plantId }: ComparisonRequest): string[] {
  return [
    houseAirUrl(scenarioId, a),
    houseAirUrl(scenarioId, b),
    ...(sensorId === null
      ? []
      : [sensorsUrl(scenarioId, "observations", a), sensorsUrl(scenarioId, "observations", b)]),
    ...(plantId === null
      ? []
      : [cropPlantUrl({ scenarioId, ...a }, plantId), cropPlantUrl({ scenarioId, ...b }, plantId)]),
  ];
}

async function json(url: string, fetchFn: typeof fetch): Promise<unknown> {
  const response = await fetchFn(url);
  if (!response.ok) {
    throw new Error(`the simulator API answered ${response.status}`);
  }
  return response.json();
}

/** A sensor's observations in a log, as seconds from the run's start and
 * values. */
function readingsOf(body: unknown, sensorId: string): [number, number][] {
  const { start, observations } = readObservations(body);
  return observations
    .filter((observation) => observation.sensor_id === sensorId)
    .map((observation): [number, number] => [
      secondsInto(start, observation.timestamp),
      observation.value,
    ]);
}

/** The readings of A and B at the moments both have one. */
function paired(a: [number, number][], b: [number, number][]): TwoSeries {
  const byMoment = new Map(b);
  const both = a.filter(([time]) => byMoment.has(time));
  return {
    at: both.map(([time]) => time),
    a: both.map(([, value]) => value),
    b: both.map(([time]) => byMoment.get(time) ?? 0),
  };
}

function plantDays(a: CropPlant, b: CropPlant, fromDay: number): Comparison["plant"] {
  const days = Math.min(a.environments.length, b.environments.length);
  const at = Array.from({ length: Math.max(0, days - fromDay) }, (_, index) => fromDay + index);
  return {
    plantId: a.plantId,
    temperature: {
      at,
      a: at.map((day) => a.environments[day]?.temperature ?? 0),
      b: at.map((day) => b.environments[day]?.temperature ?? 0),
    },
    light: {
      at,
      a: at.map((day) => a.environments[day]?.light ?? 0),
      b: at.map((day) => b.environments[day]?.light ?? 0),
    },
    thermalTime: { a: a.thermalTime, b: b.thermalTime },
  };
}

/** Fetches what a comparison draws; every failure becomes `unavailable`. */
export async function loadComparison(
  request: ComparisonRequest,
  fetchFn: typeof fetch = fetch,
): Promise<ComparisonState> {
  try {
    const bodies = await Promise.all(urls(request).map((url) => json(url, fetchFn)));
    const [houseA, houseB, ...rest] = bodies;
    const traceA = parseHouseAir(houseA);
    const traceB = parseHouseAir(houseB);
    const house = paired(
      traceA.times_s.map((time, index): [number, number] => [
        time,
        traceA.controlled.temperature_c[index] ?? 0,
      ]),
      traceB.times_s.map((time, index): [number, number] => [
        time,
        traceB.controlled.temperature_c[index] ?? 0,
      ]),
    );
    const sensor =
      request.sensorId === null
        ? null
        : {
            sensorId: request.sensorId,
            readings: paired(
              readingsOf(rest.shift(), request.sensorId),
              readingsOf(rest.shift(), request.sensorId),
            ),
          };
    const plant =
      request.plantId === null
        ? null
        : plantDays(parseCropPlant(rest.shift()), parseCropPlant(rest.shift()), request.fromDay);
    return { status: "loaded", comparison: { house, sensor, plant } };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

/** What a scenario's scene offers to compare: its first temperature sensor,
 * and the first plant it draws organ by organ, if it has them. */
export function comparable(snapshot: SceneSnapshot | null): {
  sensorId: string | null;
  plantId: string | null;
} {
  const entities = snapshot?.entities ?? [];
  const sensor = entities.find(
    (entity) => entity.kind === "SENSOR" && entity.properties.sensor_kind === "temperature",
  )?.properties.sensor_id;
  const plant = entities.find((entity) => typeof entity.properties.organ_id === "string")
    ?.properties.plant_id;
  return {
    sensorId: typeof sensor === "string" ? sensor : null,
    plantId: typeof plant === "string" ? plant : null,
  };
}
