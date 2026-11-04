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
  | {
      status: "loaded";
      trace: HouseTrace;
      /** Whether this is of an earlier moment, the one asked for on its way: the
       * air is worked out from the run's start, which takes long on a late day. */
      behind?: boolean;
    };

// Each quantity's chart, in its own units, and how its range is written.
const HEIGHT = 28;
const RANGE_DECIMALS = 1;
// Beside the run's air while the same run all off is on its way.
const ALL_OFF_ON_ITS_WAY = "all off on its way";
const CHARTED: readonly { name: string; unit: string; of: (s: HouseSeries) => number[] }[] = [
  { name: "Air", unit: "°C", of: (s) => s.temperature_c },
  { name: "Humidity", unit: "%", of: (s) => s.humidity_pct },
  { name: "CO₂", unit: "ppm", of: (s) => s.co2_ppm },
];

/** The house's air in a line, as its section folded says how it stands
 * (#273): its latest temperature, humidity and CO₂, as charted. */
export function describeHouseAir(state: HouseAirState): string {
  switch (state.status) {
    case "none":
      return "House air";
    case "loading":
      return "House air: mixing…";
    case "unavailable":
      return "House air: cannot be read";
    case "loaded": {
      const latest = CHARTED.map(({ unit, of }) => {
        const value = of(state.trace.controlled).at(-1);
        return value === undefined ? null : `${value.toFixed(RANGE_DECIMALS)} ${unit}`;
      }).filter((part) => part !== null);
      if (latest.length === 0) {
        return "House air";
      }
      return `House air: ${latest.join(", ")}${state.behind === true ? "; mixing…" : ""}`;
    }
  }
}

type LoadedHouseAir = Extract<HouseAirState, { status: "loaded" }>;

/** What the house's air has on show: the answer to the moment drawn, or, while
 * that is on its way, the last it had, said to be behind it. */
export function houseAirOnShow({
  shown,
  latest,
}: {
  shown: LoadedHouseAir | null;
  latest: HouseAirState;
}): HouseAirState {
  return latest.status === "loading" && shown !== null ? { ...shown, behind: true } : latest;
}

/** How many moments two traces share from their first: the moments of a day
 * are its minutes and then the moment asked for, so two answers of one day part
 * where the earlier one ends. */
function momentsInCommon(one: readonly number[], other: readonly number[]): number {
  let common = 0;
  while (common < one.length && one[common] === other[common]) {
    common += 1;
  }
  return common;
}

function seriesUpTo(series: HouseSeries, moments: number): HouseSeries {
  return {
    temperature_c: series.temperature_c.slice(0, moments),
    humidity_pct: series.humidity_pct.slice(0, moments),
    co2_ppm: series.co2_ppm.slice(0, moments),
    removed_kg: series.removed_kg.slice(0, moments),
    condensed_kg: series.condensed_kg.slice(0, moments),
  };
}

/** The run's own air with the run all off beside it: the answer to the same
 * moment, or until that arrives what the last answer of the same day says of the
 * moments the two share. An answer of another day shares none. Both are of one
 * run: the caller keeps no answer across runs. */
export function withAllOff(own: HouseAirState, whole: LoadedHouseAir | null): HouseAirState {
  if (own.status !== "loaded" || whole === null || whole.trace.all_off === null) {
    return own;
  }
  const common = momentsInCommon(own.trace.times_s, whole.trace.times_s);
  return common === 0
    ? own
    : { ...own, trace: { ...own.trace, all_off: seriesUpTo(whole.trace.all_off, common) } };
}

/** Where the house's air through a run is published, asked for as the
 * climate is, up to the moment drawn from the start of its day. */
export function houseAirUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/house", runParameters(run));
}

/** The same without the run all off, which is apart because it takes long the
 * first time a far moment is asked of it: nothing of the run itself waits. */
export function ownHouseAirUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/house", [...runParameters(run), "all_off=0"]);
}

const UNEXPECTED = "the house's air is not what the viewer expects";
const readHouseAir = contractReader<HouseTrace>(HOUSE_AIR_SCHEMA, UNEXPECTED);

/** A house trace, checked rather than trusted: each series has a value at
 * each of its moments. */
export function parseHouseAir(body: unknown): HouseTrace {
  const trace = readHouseAir(body);
  const moments = trace.times_s.length;
  const series = [trace.controlled, ...(trace.all_off === null ? [] : [trace.all_off])].flatMap(
    (run) => Object.values(run),
  );
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
        const off = trace.all_off === null ? [] : of(trace.all_off);
        const low = Math.min(...run, ...off);
        const high = Math.max(...run, ...off);
        const latest = run.at(-1) ?? low;
        const lastOff = off.at(-1);
        const beside =
          lastOff === undefined || off.length < run.length
            ? ALL_OFF_ON_ITS_WAY
            : `all off ${lastOff.toFixed(RANGE_DECIMALS)} ${unit}`;
        const text = `${name} ${latest.toFixed(RANGE_DECIMALS)} ${unit}, ${beside}`;
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
              {off.length > 0 && (
                <polyline
                  className="house-air-off"
                  points={polyline(trace.times_s.slice(0, off.length), off, low, high)}
                />
              )}
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
