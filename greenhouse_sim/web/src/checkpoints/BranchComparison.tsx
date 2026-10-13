import { useLoad } from "../useLoad";
import { type ComparisonRequest, comparisonKey, loadComparison, type TwoSeries } from "./branches";
import type { CheckpointSummary } from "./checkpoints";

// Each chart, in its own units: A drawn solid, B dashed.
const WIDTH = 240;
const HEIGHT = 32;
const POINT_DECIMALS = 1;

function polyline(at: number[], values: number[], low: number, high: number): string {
  const first = at[0] ?? 0;
  const span = (at.at(-1) ?? first) - first;
  const x = (point: number) => (span === 0 ? WIDTH / 2 : ((point - first) / span) * WIDTH);
  const y = (value: number) =>
    high === low ? HEIGHT / 2 : HEIGHT - ((value - low) / (high - low)) * HEIGHT;
  return at
    .map(
      (point, index) =>
        `${x(point).toFixed(POINT_DECIMALS)},${y(values[index] ?? low).toFixed(POINT_DECIMALS)}`,
    )
    .join(" ");
}

/** Two branches' latest values in words: "A 18.9 °C, B 16.2 °C". */
export function describeBranches(series: TwoSeries, unit: string, decimals = 1): string {
  const a = series.a.at(-1);
  const b = series.b.at(-1);
  if (a === undefined || b === undefined) {
    return "nothing yet";
  }
  return `A ${a.toFixed(decimals)} ${unit}, B ${b.toFixed(decimals)} ${unit}`;
}

function TwoLines({
  testId,
  name,
  series,
  unit,
}: {
  testId: string;
  name: string;
  series: TwoSeries;
  unit: string;
}) {
  const values = [...series.a, ...series.b];
  const low = Math.min(...values);
  const high = Math.max(...values);
  return (
    <div className="house-air-row">
      <span data-testid={testId}>
        {name}: {describeBranches(series, unit)}
      </span>
      <svg
        className="house-air-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${name}, branch A and branch B`}
      >
        <polyline className="branch-a" points={polyline(series.at, series.a, low, high)} />
        <polyline className="branch-b" points={polyline(series.at, series.b, low, high)} />
      </svg>
    </div>
  );
}

/**
 * Two branches from the same checkpoint charted side by side (P09.5): A,
 * the checkpoint's run carried on unchanged, and B, the run drawn, at the
 * moment drawn: the house's air through its day, a sensor's readings
 * through it, and a plant's days since the checkpoint with how far it has
 * developed.
 */
export function BranchComparison({
  checkpoint,
  request,
  time,
}: {
  checkpoint: CheckpointSummary;
  request: ComparisonRequest;
  time: number;
}) {
  const before = time < checkpoint.timeS;
  const state = useLoad(before ? null : request, loadComparison, { key: comparisonKey });
  return (
    <section className="branches" aria-label="Branches">
      <p data-testid="branches-heading">
        A: day {checkpoint.day}'s checkpoint, carried on as it was; B: the run drawn.
      </p>
      {before && <p>The moment drawn lies before the checkpoint.</p>}
      {state.status === "loading" && <p>Running both branches…</p>}
      {state.status === "unavailable" && (
        <p role="alert">The branches cannot be compared: {state.reason}.</p>
      )}
      {state.status === "loaded" && (
        <figure aria-label="Branch comparison">
          <TwoLines
            testId="branches-house"
            name="House air"
            series={state.comparison.house}
            unit="°C"
          />
          {state.comparison.sensor !== null && (
            <TwoLines
              testId="branches-sensor"
              name={state.comparison.sensor.sensorId.replaceAll("_", " ")}
              series={state.comparison.sensor.readings}
              unit="°C"
            />
          )}
          {state.comparison.plant !== null && (
            <>
              <TwoLines
                testId="branches-plant-air"
                name={`${state.comparison.plant.plantId}'s days`}
                series={state.comparison.plant.temperature}
                unit="°C"
              />
              <p data-testid="branches-plant-development">
                Developed: A {Math.round(state.comparison.plant.thermalTime.a)} °Cd, B{" "}
                {Math.round(state.comparison.plant.thermalTime.b)} °Cd
              </p>
            </>
          )}
        </figure>
      )}
    </section>
  );
}
