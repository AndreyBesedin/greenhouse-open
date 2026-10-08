import { describeTime } from "../fields/ClimateTime";
import { chartRange } from "../fields/ProbeCharts";
import { formatValue } from "../readouts";
import {
  latestReading,
  latestTruth,
  type SensorReadings,
  type SensorReadingsState,
  sensorSeries,
} from "./readings";

const MS_PER_SECOND = 1000;
// The chart's size in its own units, and its readings' dots.
const WIDTH = 240;
const HEIGHT = 70;
const DOT_RADIUS = 2;

/** Seconds from a run's start to an instant, as the simulator stamps both. */
function secondsInto(start: string, instant: string): number {
  return (Date.parse(instant) - Date.parse(start)) / MS_PER_SECOND;
}

/** The truth as a line, and the readings as dots, across the run so far. */
function SensorChart({
  readings,
  sensorId,
  until,
}: {
  readings: SensorReadings;
  sensorId: string;
  until: number;
}) {
  const { observed, truth } = sensorSeries(readings, sensorId);
  if (observed.length === 0 && truth.length === 0) {
    return null;
  }
  const range = chartRange(
    observed.map(([, value]) => value),
    truth.map(([, value]) => value),
  );
  const span = Math.max(until, ...truth.map(([time]) => time), 1);
  const x = (time: number) => (time / span) * WIDTH;
  const y = (value: number) => HEIGHT - ((value - range.min) / (range.max - range.min)) * HEIGHT;
  return (
    <svg
      className="sensor-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${sensorId} read against the truth, ${formatValue(range.min)} to ${formatValue(range.max)}`}
      data-testid="sensor-chart"
    >
      <polyline
        className="sensor-chart-truth"
        points={truth
          .map(([time, value]) => `${x(time).toFixed(1)},${y(value).toFixed(1)}`)
          .join(" ")}
      />
      {observed.map(([time, value]) => (
        <circle
          key={time}
          className="sensor-chart-reading"
          cx={x(time)}
          cy={y(value)}
          r={DOT_RADIUS}
        />
      ))}
    </svg>
  );
}

/**
 * A selected sensor's latest reading at the moment drawn, a chart of its
 * readings against the truth through the run so far, and, apart, in a panel
 * marked as QA's, what it truly sampled: the truth a policy never sees, and
 * a switch to see its readings as a clean sensor's.
 */
export function SensorPanel({
  sensorId,
  unit,
  state,
  until,
  imperfect,
  onImperfect,
}: {
  sensorId: string;
  unit: string;
  state: SensorReadingsState;
  /** The moment drawn, in seconds into the run. */
  until: number;
  /** Whether its readings are as it errs, or as a clean sensor's. */
  imperfect: boolean;
  onImperfect: (imperfect: boolean) => void;
}) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <section className="sensor-panel" aria-label="Sensor">
        <p data-testid="sensor-status">
          {state.status === "loading"
            ? "Reading the sensor…"
            : `The sensor cannot be read: ${state.reason}.`}
        </p>
      </section>
    );
  }
  const { readings } = state;
  const reading = latestReading(readings, sensorId);
  const truth = latestTruth(readings, sensorId);
  return (
    <section className="sensor-panel" aria-label="Sensor">
      <p data-testid="sensor-reading">
        {reading === undefined
          ? "No reading: nothing gives this quantity yet."
          : `${formatValue(reading.value)} ${unit} at ${describeTime(
              secondsInto(readings.start, reading.timestamp),
            )}`}
      </p>
      <SensorChart readings={readings} sensorId={sensorId} until={until} />
      <aside className="sensor-truth" aria-label="Truth, for QA only">
        <span>Truth, for QA only:</span>{" "}
        <span data-testid="sensor-truth">
          {truth === undefined || truth.value === null
            ? "none"
            : `${formatValue(truth.value)} ${truth.unit} at ${describeTime(truth.timeS)}`}
        </span>
        <label>
          <input
            type="checkbox"
            checked={imperfect}
            onChange={(event) => onImperfect(event.target.checked)}
          />{" "}
          Imperfections
        </label>
      </aside>
    </section>
  );
}
