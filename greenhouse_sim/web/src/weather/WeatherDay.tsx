import type { WeatherDay, WeatherDayState, WeatherState } from "./weather";

// Each quantity's chart, in its own units: wide and short.
const WIDTH = 240;
const HEIGHT = 28;
const POINT_DECIMALS = 1;
const RANGE_DECIMALS = 1;
// What is charted through the day, its unit, and its colour.
const CHARTED: readonly {
  name: string;
  unit: string;
  className: string;
  of: (state: WeatherState) => number;
}[] = [
  { name: "Air", unit: "°C", className: "day-temperature", of: (s) => s.air_temperature_c },
  { name: "Humidity", unit: "%", className: "day-humidity", of: (s) => s.relative_humidity_pct },
  { name: "Wind", unit: "m/s", className: "day-wind", of: (s) => s.wind_speed_m_s },
];

/** One quantity through the day, as a line, with the moment drawn marked
 * across it; flat in the middle if it never changes. */
function DayLine({
  day,
  name,
  unit,
  className,
  of,
  time,
}: {
  day: WeatherDay;
  name: string;
  unit: string;
  className: string;
  of: (state: WeatherState) => number;
  time: number;
}) {
  const values = day.weather.map(of);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = Math.max(...day.timesS, 1);
  const x = (seconds: number) => (seconds / span) * WIDTH;
  const y = (value: number) =>
    high === low ? HEIGHT / 2 : HEIGHT - ((value - low) / (high - low)) * HEIGHT;
  const points = day.timesS
    .map((seconds, index) => {
      const value = values[index] ?? low;
      return `${x(seconds).toFixed(POINT_DECIMALS)},${y(value).toFixed(POINT_DECIMALS)}`;
    })
    .join(" ");
  const range =
    high === low
      ? `${low.toFixed(RANGE_DECIMALS)} ${unit}`
      : `${low.toFixed(RANGE_DECIMALS)} to ${high.toFixed(RANGE_DECIMALS)} ${unit}`;
  return (
    <div className="weather-day-row">
      <span data-testid={`weather-day-${className}`}>{`${name}, ${range}`}</span>
      <svg
        className="weather-day-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${name} through the day, ${range}`}
      >
        <polyline className={className} points={points} />
        <line
          className="weather-day-now"
          data-testid="weather-day-now"
          x1={x(time)}
          x2={x(time)}
          y1={0}
          y2={HEIGHT}
        />
      </svg>
    </div>
  );
}

/** The weather through the runs' first day: the air's temperature, its
 * humidity and the wind's speed, each from its least to its most, with the
 * moment drawn marked across them. */
export function WeatherDayChart({ state, time }: { state: WeatherDayState; time: number }) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <p className="weather-day" data-testid="weather-day">
        {state.status === "loading"
          ? "Reading the day's weather…"
          : `The day's weather cannot be read: ${state.reason}.`}
      </p>
    );
  }
  return (
    <figure className="weather-day" data-testid="weather-day" aria-label="The day's weather">
      {CHARTED.map((charted) => (
        <DayLine key={charted.name} day={state.day} time={time} {...charted} />
      ))}
    </figure>
  );
}
