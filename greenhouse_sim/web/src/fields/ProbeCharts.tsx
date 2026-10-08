import { pairsText, type ScheduledCommand, scheduleText } from "../scene/source";
import type { Point3 } from "../world";
import { describeTime } from "./ClimateTime";
import { probesText } from "./probes";
import { CLIMATE_RUN_S } from "./source";

/** What a probe reads at each moment of a run: temperature (°C), relative
 * humidity (%) and air speed (m/s). */
export interface Readings {
  temperature_c: number[];
  humidity_pct: number[];
  speed_m_s: number[];
}

/** What probes read through a climate run and the same run with everything
 * off (`GET /api/scenarios/{id}/climate/probes`). */
export interface ClimateProbes {
  times_s: number[];
  probes: { point: Point3; controlled: Readings; all_off: Readings }[];
}

export type ProbeChartsState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; probes: ClimateProbes };

function isNumbers(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((item) => typeof item === "number");
}

function isReadings(value: unknown): value is Readings {
  return (
    typeof value === "object" &&
    value !== null &&
    "temperature_c" in value &&
    isNumbers(value.temperature_c) &&
    "humidity_pct" in value &&
    isNumbers(value.humidity_pct) &&
    "speed_m_s" in value &&
    isNumbers(value.speed_m_s)
  );
}

/** Whether a body is probes' readings through a run, as the simulator sends
 * them. */
export function isClimateProbes(body: unknown): body is ClimateProbes {
  return (
    typeof body === "object" &&
    body !== null &&
    "times_s" in body &&
    isNumbers(body.times_s) &&
    "probes" in body &&
    Array.isArray(body.probes) &&
    body.probes.every(
      (probe: unknown) =>
        typeof probe === "object" &&
        probe !== null &&
        "controlled" in probe &&
        isReadings(probe.controlled) &&
        "all_off" in probe &&
        isReadings(probe.all_off),
    )
  );
}

/** Where probes' readings through a scenario's climate run are published,
 * asked for as its climate is, up to the moment drawn. */
export function probeChartsUrl(
  scenarioId: string,
  run: {
    probes: readonly Point3[];
    levels?: Readonly<Record<string, number>> | undefined;
    openings?: Readonly<Record<string, number>> | undefined;
    schedule?: readonly ScheduledCommand[] | undefined;
    time?: number | undefined;
  },
): string {
  const parts = [
    `probes=${probesText(run.probes)}`,
    ...(pairsText(run.levels) === "" ? [] : [`set=${pairsText(run.levels)}`]),
    ...(pairsText(run.openings) === "" ? [] : [`open=${pairsText(run.openings)}`]),
    ...(scheduleText(run.schedule) === "" ? [] : [`schedule=${scheduleText(run.schedule)}`]),
    ...(run.time === undefined || run.time === 0 ? [] : [`t=${run.time}`]),
  ];
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/probes?${parts.join("&")}`;
}

/** Fetches and checks probes' readings; every failure becomes a state. */
export async function loadProbeCharts(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<ProbeChartsState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    const body: unknown = await response.json();
    return isClimateProbes(body)
      ? { status: "loaded", probes: body }
      : { status: "unavailable", reason: "the readings are not what the viewer expects" };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

// A chart's size in its own units.
const WIDTH = 240;
const HEIGHT = 70;

/** The quantities charted, each with its unit and how many decimals it is
 * read to. */
export const CHARTED = [
  { key: "temperature_c", name: "temperature", unit: "°C" },
  { key: "humidity_pct", name: "humidity", unit: "%" },
  { key: "speed_m_s", name: "air speed", unit: "m/s" },
] as const;

/** The range a chart spans: its two runs' lowest and highest values, a
 * little apart if they are one. */
export function chartRange(...series: number[][]): { min: number; max: number } {
  const values = series.flat();
  const min = Math.min(...values);
  const max = Math.max(...values);
  return min === max ? { min: min - 1, max: max + 1 } : { min, max };
}

/** A run's values as an SVG polyline's points: across the run's hour, and
 * up its range, the highest at the top. */
export function chartPoints(
  times: readonly number[],
  values: readonly number[],
  range: { min: number; max: number },
): string {
  return values
    .map((value, index) => {
      const x = ((times[index] ?? 0) / CLIMATE_RUN_S) * WIDTH;
      const y = HEIGHT - ((value - range.min) / (range.max - range.min)) * HEIGHT;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function format(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(2);
}

/**
 * Each probe's temperature, relative humidity and air speed through the run,
 * charted beside the same run with everything off: plain SVG, a line for
 * each run across the run's hour, the moment drawn marked, and what both
 * read then.
 */
export function ProbeCharts({ state, time }: { state: ProbeChartsState; time: number }) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <p className="probe-charts" data-testid="probe-charts-status">
        {state.status === "loading"
          ? "Reading the probes through the run…"
          : `The probes cannot be read: ${state.reason}.`}
      </p>
    );
  }
  const { times_s: times, probes } = state.probes;
  const last = times.length - 1;
  const cursor = (time / CLIMATE_RUN_S) * WIDTH;
  return (
    <section className="probe-charts" aria-label="Probe charts">
      <p className="probe-charts-key">
        <span className="probe-charts-controlled">—</span> this run,{" "}
        <span className="probe-charts-off">- -</span> all off, at {describeTime(times[last] ?? 0)}
      </p>
      {probes.map((probe, index) => {
        const name = `P${index + 1}`;
        return (
          <figure key={name}>
            <figcaption>{name}</figcaption>
            {CHARTED.map(({ key, name: quantity, unit }) => {
              const controlled = probe.controlled[key];
              const off = probe.all_off[key];
              const range = chartRange(controlled, off);
              return (
                <div key={key} className="probe-chart">
                  <svg
                    viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                    role="img"
                    aria-label={`${name} ${quantity}, ${format(range.min)} to ${format(range.max)} ${unit}`}
                  >
                    <line
                      className="probe-chart-cursor"
                      x1={cursor}
                      x2={cursor}
                      y1={0}
                      y2={HEIGHT}
                    />
                    <polyline
                      className="probe-charts-off"
                      points={chartPoints(times, off, range)}
                    />
                    <polyline
                      className="probe-charts-controlled"
                      points={chartPoints(times, controlled, range)}
                    />
                  </svg>
                  <span data-testid={`chart-${name}-${key}`}>
                    {quantity} {format(controlled[last])} {unit}, all off {format(off[last])} {unit}
                  </span>
                </div>
              );
            })}
          </figure>
        );
      })}
    </section>
  );
}
