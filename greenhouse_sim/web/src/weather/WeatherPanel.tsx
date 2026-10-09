import { DEFAULT_WEATHER } from "../scenarios";
import { WeatherDayChart } from "./WeatherDay";
import {
  compassPoint,
  describeSun,
  describeWind,
  type WeatherAtAMoment,
  type WeatherDayState,
  type WeatherStateOfLoad,
} from "./weather";

// The compass's size in its own units, its needle's length, its head's
// length and half its width, and where the north mark stands.
const COMPASS_SIZE = 32;
const NEEDLE_LENGTH = 12;
const HEAD_LENGTH = 4;
const HEAD_HALF_WIDTH = 3;
const NORTH_MARK_Y = 8;
const HALF_TURN_DEG = 180;
// Temperatures to a tenth of a degree, the rest to the unit.
const TEMPERATURE_DECIMALS = 1;
const LATITUDE_DECIMALS = 2;

/** When a moment is, at the site: "1 Jan 2026, 00:10". */
export function localTime(weather: WeatherAtAMoment): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: weather.site.time_zone,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(weather.moment));
}

/** The site, in words: "52.00° N, 4.50° E, Europe/Amsterdam; x points E". */
export function describeSite(weather: WeatherAtAMoment): string {
  const { latitude_deg, longitude_deg, time_zone, x_bearing_deg } = weather.site;
  const north = `${Math.abs(latitude_deg).toFixed(LATITUDE_DECIMALS)}° ${latitude_deg < 0 ? "S" : "N"}`;
  const east = `${Math.abs(longitude_deg).toFixed(LATITUDE_DECIMALS)}° ${longitude_deg < 0 ? "W" : "E"}`;
  return `${north}, ${east}, ${time_zone}; x points ${compassPoint(x_bearing_deg)}`;
}

/** A compass, north up, with a needle along the way the wind blows. */
function WindCompass({ weather }: { weather: WeatherAtAMoment }) {
  const middle = COMPASS_SIZE / 2;
  const from = weather.weather.wind_direction_deg;
  const blowing = weather.weather.wind_speed_m_s > 0 && from !== null;
  const towards = ((from ?? 0) + HALF_TURN_DEG) % (2 * HALF_TURN_DEG);
  const tip = middle - NEEDLE_LENGTH / 2;
  const tail = middle + NEEDLE_LENGTH / 2;
  return (
    <svg
      className="wind-compass"
      viewBox={`0 0 ${COMPASS_SIZE} ${COMPASS_SIZE}`}
      role="img"
      aria-label={`compass: wind ${describeWind(weather.weather)}`}
      data-testid="wind-compass"
    >
      <circle className="wind-compass-ring" cx={middle} cy={middle} r={middle - 1} />
      <text className="wind-compass-north" x={middle} y={NORTH_MARK_Y} textAnchor="middle">
        N
      </text>
      {blowing && (
        <g transform={`rotate(${towards} ${middle} ${middle})`} data-testid="wind-needle">
          <line className="wind-compass-needle" x1={middle} y1={tail} x2={middle} y2={tip} />
          <polygon
            className="wind-compass-head"
            points={`${middle},${tip} ${middle - HEAD_HALF_WIDTH},${tip + HEAD_LENGTH} ${middle + HEAD_HALF_WIDTH},${tip + HEAD_LENGTH}`}
          />
        </g>
      )}
    </svg>
  );
}

/** A weather's name in words: a preset's, or "its own" for the scenario's. */
export function weatherName(name: string): string {
  return name === DEFAULT_WEATHER ? "its own" : name.replaceAll("_", " ");
}

/**
 * The weather outside at the moment drawn: a line saying when the moment is
 * at the site, the air's temperature and the wind, with a compass needle
 * along it; and, opened, which weather the scenario is run under, the air's
 * humidity and CO₂, the wind's bearing, the pressure, where the site is,
 * and the weather through the day.
 */
export function WeatherPanel({
  state,
  day = { status: "none" },
  weathers = [],
  chosen,
  time = 0,
  onChoose,
}: {
  state: WeatherStateOfLoad;
  day?: WeatherDayState;
  /** The weathers the scenario can be run under, its own first. */
  weathers?: readonly string[];
  /** The one it is run under, if not its own. */
  chosen?: string | undefined;
  /** The moment drawn, in seconds from the run's start. */
  time?: number;
  onChoose?: (weather: string | undefined) => void;
}) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <section className="weather-panel" aria-label="Weather">
        <p data-testid="weather-summary">
          {state.status === "loading"
            ? "Reading the weather…"
            : `The weather cannot be read: ${state.reason}.`}
        </p>
      </section>
    );
  }
  const { weather } = state;
  const outside = weather.weather;
  const temperature = `${outside.air_temperature_c.toFixed(TEMPERATURE_DECIMALS)} °C`;
  const wind = describeWind(outside);
  const bearing =
    outside.wind_speed_m_s > 0 && outside.wind_direction_deg !== null
      ? ` (${Math.round(outside.wind_direction_deg)}°)`
      : "";
  return (
    <section className="weather-panel" aria-label="Weather">
      <details>
        <summary className="weather-heading">
          <span data-testid="weather-summary">
            {`Outside at ${localTime(weather)}: ${temperature}, wind ${wind}.`}
          </span>
          <WindCompass weather={weather} />
        </summary>
        {onChoose !== undefined && weathers.length > 1 && (
          <label className="weather-choice">
            Run under{" "}
            <select
              aria-label="Weather to run under"
              value={chosen ?? DEFAULT_WEATHER}
              onChange={(event) =>
                onChoose(event.target.value === DEFAULT_WEATHER ? undefined : event.target.value)
              }
            >
              {weathers.map((name) => (
                <option key={name} value={name}>
                  {weatherName(name)}
                </option>
              ))}
            </select>
          </label>
        )}
        <dl>
          <dt>Air</dt>
          <dd data-testid="weather-air">
            {`${temperature}, ${Math.round(outside.relative_humidity_pct)}% RH, ${Math.round(outside.co2_ppm)} ppm CO₂`}
          </dd>
          <dt>Wind</dt>
          <dd data-testid="weather-wind">{`${wind}${bearing}`}</dd>
          <dt>Sun</dt>
          <dd data-testid="weather-sun">{describeSun(weather.sun)}</dd>
          <dt>Pressure</dt>
          <dd data-testid="weather-pressure">
            {`${Math.round(outside.barometric_pressure_hpa)} hPa`}
          </dd>
          <dt>Site</dt>
          <dd data-testid="weather-site">{describeSite(weather)}</dd>
        </dl>
        <WeatherDayChart state={day} time={time} />
      </details>
    </section>
  );
}
