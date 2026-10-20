import { CHART_WIDTH, polylinePoints } from "../charts/chart";
import { DAY_S, dayStart } from "../clock";
import { contractReader, loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { HOUSE_AIR_SCHEMA } from "./generated/houseAirSchema";
import type { HouseSeries, HouseTrace } from "./generated/houseAirTypes";

// The house's air as one well-mixed volume at each moment of a trace,
// through a climate run, and through the same run with everything off, at
// seconds from its start (`GET .../climate/house`).
export type { HouseSeries, HouseTrace };

export type HouseAirState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; trace: HouseTrace };

// Each quantity's chart, in its own units, and how its range is written.
const HEIGHT = 28;
const RANGE_DECIMALS = 1;
const CHARTED: readonly { name: string; unit: string; of: (s: HouseSeries) => number[] }[] = [
  { name: "Air", unit: "°C", of: (s) => s.temperature_c },
  { name: "Humidity", unit: "%", of: (s) => s.humidity_pct },
  { name: "CO₂", unit: "ppm", of: (s) => s.co2_ppm },
];

/** Where the house's air through a run is published, asked for as the
 * climate is, up to the moment drawn from the start of its day. */
export function houseAirUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/house", runParameters(run));
}

const UNEXPECTED = "the house's air is not what the viewer expects";
const readHouseAir = contractReader<HouseTrace>(HOUSE_AIR_SCHEMA, UNEXPECTED);

/** A house trace, checked rather than trusted: each series has a value at
 * each of its moments. */
export function parseHouseAir(body: unknown): HouseTrace {
  const trace = readHouseAir(body);
  const moments = trace.times_s.length;
  const series = [trace.controlled, trace.all_off].flatMap((run) => Object.values(run));
  if (series.some((values) => values.length !== moments)) {
    throw new Error(UNEXPECTED);
  }
  return trace;
}

/** Fetches the house's air through a run; every failure becomes a state. */
export async function loadHouseAir(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<HouseAirState> {
  const answer = await loadJson(url, parseHouseAir, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", trace: answer.value } : answer;
}

function polyline(times: number[], values: number[], low: number, high: number): string {
  // Across the day of the trace's last moment, from its start.
  const from = dayStart(times.at(-1) ?? 0);
  const x = (seconds: number) => ((seconds - from) / DAY_S) * CHART_WIDTH;
  return polylinePoints(times.map(x), values, { min: low, max: high }, HEIGHT);
}

/**
 * The house's air as one well-mixed volume through the moment's day up to
 * the moment drawn, across the day: its temperature, humidity and
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
              viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`The house's ${name.toLowerCase()} through the day`}
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
