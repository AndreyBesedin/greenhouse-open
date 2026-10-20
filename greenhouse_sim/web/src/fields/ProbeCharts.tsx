import { CHART_WIDTH, polylinePoints } from "../charts/chart";
import { contractCheck, loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import type { Point3 } from "../world";
import { describeTime } from "./ClimateTime";
import { CLIMATE_PROBES_SCHEMA } from "./generated/probesSchema";
import type { ClimateProbes, Readings } from "./generated/probesTypes";
import { probesText } from "./probes";
import { GRID_RUN_S } from "./source";

// What a probe reads at each moment of a run, temperature (°C), relative
// humidity (%) and air speed (m/s), through a climate run and the same run
// with everything off (`GET /api/scenarios/{id}/climate/probes`).
export type { ClimateProbes, Readings };

export type ProbeChartsState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; probes: ClimateProbes };

const checkProbes = contractCheck<ClimateProbes>(CLIMATE_PROBES_SCHEMA, "the readings");

/** Whether a body is probes' readings through a run, as the simulator sends
 * them. */
export function isClimateProbes(body: unknown): body is ClimateProbes {
  return checkProbes(body).ok;
}

/** Where probes' readings through a scenario's climate run are published,
 * asked for as its climate is, up to the moment drawn. */
export function probeChartsUrl(
  scenarioId: string,
  run: RunParts & { probes: readonly Point3[] },
): string {
  return scenarioUrl(scenarioId, "climate/probes", [
    `probes=${probesText(run.probes)}`,
    ...runParameters(run),
  ]);
}

/** Fetches and checks probes' readings; every failure becomes a state. */
export async function loadProbeCharts(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<ProbeChartsState> {
  const answer = await loadJson(url, climateProbesOf, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", probes: answer.value } : answer;
}

function climateProbesOf(body: unknown): ClimateProbes {
  if (!isClimateProbes(body)) {
    throw new Error("the readings are not what the viewer expects");
  }
  return body;
}

// A chart's size in its own units.
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

/** Where a moment lies across a chart that starts at `from`, as wide as a
 * grid run's longest. */
function across(time: number, from: number): number {
  return ((time - from) / GRID_RUN_S) * CHART_WIDTH;
}

/** A run's values as an SVG polyline's points: across the grid run they
 * were read from, from its start, and up their range, the highest at the
 * top. */
export function chartPoints(
  times: readonly number[],
  values: readonly number[],
  range: { min: number; max: number },
): string {
  const from = times[0] ?? 0;
  const xs = values.map((_, index) => across(times[index] ?? 0, from));
  return polylinePoints(xs, values, range, HEIGHT);
}

function format(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(2);
}

/**
 * Each probe's temperature, relative humidity and air speed through the grid
 * run that draws the moment, from its start, charted beside the same run
 * with everything off: plain SVG, a line for each run across the grid run's
 * two hours, the moment drawn marked, and what both read then.
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
  const cursor = across(time, times[0] ?? 0);
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
                    viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
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
