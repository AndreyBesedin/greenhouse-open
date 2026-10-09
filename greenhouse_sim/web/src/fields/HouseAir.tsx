import { pairsText, type ScheduledCommand, scheduleText, weatherParameter } from "../scene/source";
import { CLIMATE_RUN_S } from "./source";

/** The house's air as one well-mixed volume at each moment of a trace. */
export interface HouseSeries {
  temperature_c: number[];
  humidity_pct: number[];
  co2_ppm: number[];
  removed_kg: number[];
  condensed_kg: number[];
}

/** The house's air through a climate run, and through the same run with
 * everything off, at seconds from its start (`GET .../climate/house`). */
export interface HouseTrace {
  times_s: number[];
  controlled: HouseSeries;
  all_off: HouseSeries;
}

export type HouseAirState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; trace: HouseTrace };

const SERIES = ["temperature_c", "humidity_pct", "co2_ppm", "removed_kg", "condensed_kg"] as const;
// Each quantity's chart, in its own units, and how its range is written.
const WIDTH = 240;
const HEIGHT = 28;
const POINT_DECIMALS = 1;
const RANGE_DECIMALS = 1;
const CHARTED: readonly { name: string; unit: string; of: (s: HouseSeries) => number[] }[] = [
  { name: "Air", unit: "°C", of: (s) => s.temperature_c },
  { name: "Humidity", unit: "%", of: (s) => s.humidity_pct },
  { name: "CO₂", unit: "ppm", of: (s) => s.co2_ppm },
];

/** Where the house's air through a run is published, asked for as the
 * climate is, up to the moment drawn. */
export function houseAirUrl(
  scenarioId: string,
  run: {
    layout?: string | undefined;
    levels?: Readonly<Record<string, number>> | undefined;
    openings?: Readonly<Record<string, number>> | undefined;
    schedule?: readonly ScheduledCommand[] | undefined;
    time?: number | undefined;
    weather?: string | undefined;
  },
): string {
  const parts = [
    ...(run.layout === undefined ? [] : [`layout=${encodeURIComponent(run.layout)}`]),
    ...(pairsText(run.levels) === "" ? [] : [`set=${pairsText(run.levels)}`]),
    ...(pairsText(run.openings) === "" ? [] : [`open=${pairsText(run.openings)}`]),
    ...(scheduleText(run.schedule) === "" ? [] : [`schedule=${scheduleText(run.schedule)}`]),
    ...(run.time === undefined || run.time === 0 ? [] : [`t=${run.time}`]),
    ...weatherParameter(run.weather),
  ];
  const query = parts.length === 0 ? "" : `?${parts.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/house${query}`;
}

function isSeries(value: unknown, length: number): value is HouseSeries {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const fields = value as Record<string, unknown>;
  return SERIES.every((name) => {
    const series = fields[name];
    return (
      Array.isArray(series) &&
      series.length === length &&
      series.every((item) => typeof item === "number")
    );
  });
}

/** A house trace, checked rather than trusted. */
export function parseHouseAir(body: unknown): HouseTrace {
  if (typeof body !== "object" || body === null) {
    throw new Error("the house's air is not what the viewer expects");
  }
  const fields = body as Record<string, unknown>;
  const times = fields.times_s;
  if (
    !Array.isArray(times) ||
    !times.every((time) => typeof time === "number") ||
    !isSeries(fields.controlled, times.length) ||
    !isSeries(fields.all_off, times.length)
  ) {
    throw new Error("the house's air is not what the viewer expects");
  }
  return { times_s: times, controlled: fields.controlled, all_off: fields.all_off };
}

/** Fetches the house's air through a run; every failure becomes a state. */
export async function loadHouseAir(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<HouseAirState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", trace: parseHouseAir(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}

function polyline(times: number[], values: number[], low: number, high: number): string {
  const x = (seconds: number) => (seconds / CLIMATE_RUN_S) * WIDTH;
  const y = (value: number) =>
    high === low ? HEIGHT / 2 : HEIGHT - ((value - low) / (high - low)) * HEIGHT;
  return times
    .map((time, index) => {
      const value = values[index] ?? low;
      return `${x(time).toFixed(POINT_DECIMALS)},${y(value).toFixed(POINT_DECIMALS)}`;
    })
    .join(" ");
}

/**
 * The house's air as one well-mixed volume through the climate run up to
 * the moment drawn, across the run's length: its temperature, humidity and
 * CO₂, each from its least to its most, the run with everything off dashed
 * beside it.
 */
export function HouseAir({ state }: { state: HouseAirState }) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <p className="house-air" data-testid="house-air">
        {state.status === "loading"
          ? "Mixing the house's air…"
          : `The house's air cannot be read: ${state.reason}.`}
      </p>
    );
  }
  const { trace } = state;
  return (
    <figure className="house-air" data-testid="house-air" aria-label="House air">
      {CHARTED.map(({ name, unit, of }) => {
        const run = of(trace.controlled);
        const off = of(trace.all_off);
        const low = Math.min(...run, ...off);
        const high = Math.max(...run, ...off);
        const latest = run.at(-1) ?? low;
        const text = `${name} ${latest.toFixed(RANGE_DECIMALS)} ${unit}, all off ${(off.at(-1) ?? low).toFixed(RANGE_DECIMALS)} ${unit}`;
        return (
          <div className="house-air-row" key={name}>
            <span data-testid={`house-air-${unit}`}>{text}</span>
            <svg
              className="house-air-chart"
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`The house's ${name.toLowerCase()} through the run`}
            >
              <polyline
                className="house-air-off"
                points={polyline(trace.times_s, off, low, high)}
              />
              <polyline
                className="house-air-run"
                points={polyline(trace.times_s, run, low, high)}
              />
            </svg>
          </div>
        );
      })}
    </figure>
  );
}
