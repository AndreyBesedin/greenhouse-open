import { describeTime } from "../fields/ClimateTime";
import { formatValue } from "../readouts";
import { latestReading, latestTruth, type SensorReadingsState } from "./readings";

const MS_PER_SECOND = 1000;

/** Seconds from a run's start to an instant, as the simulator stamps both. */
function secondsInto(start: string, instant: string): number {
  return (Date.parse(instant) - Date.parse(start)) / MS_PER_SECOND;
}

/**
 * A selected sensor's latest reading at the moment drawn, and, apart, in a
 * panel marked as QA's, what it truly sampled then: the truth a policy never
 * sees.
 */
export function SensorPanel({
  sensorId,
  unit,
  state,
}: {
  sensorId: string;
  unit: string;
  state: SensorReadingsState;
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
      <aside className="sensor-truth" aria-label="Truth, for QA only">
        <span>Truth, for QA only:</span>{" "}
        <span data-testid="sensor-truth">
          {truth === undefined || truth.value === null
            ? "none"
            : `${formatValue(truth.value)} ${truth.unit} at ${describeTime(truth.timeS)}`}
        </span>
      </aside>
    </section>
  );
}
