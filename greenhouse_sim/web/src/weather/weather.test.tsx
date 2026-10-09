import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { WeatherDayChart } from "./WeatherDay";
import { describeSite, localTime, WeatherPanel, weatherName } from "./WeatherPanel";
import {
  compassPoint,
  describeWind,
  loadWeather,
  loadWeatherDay,
  parseWeather,
  parseWeatherDay,
  type WeatherAtAMoment,
  weatherDayUrl,
  weatherUrl,
  windOverlays,
} from "./weather";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);

// The weather as the simulator sends it, with a wind from the west.
const WESTERLY_BODY = {
  site: {
    latitude_deg: 52,
    longitude_deg: 4.5,
    elevation_m: 0,
    time_zone: "Europe/Amsterdam",
    x_bearing_deg: 90,
  },
  moment: "2025-12-31T23:10:00Z",
  time_s: 600,
  weather: {
    air_temperature_c: 8,
    relative_humidity_pct: 90,
    co2_ppm: 420,
    wind_speed_m_s: 3,
    wind_direction_deg: 270,
    barometric_pressure_hpa: 1013.25,
    global_radiation_w_m2: 0,
    cloud_cover_pct: 0,
  },
  wind_m_s: { x: 3, y: 0, z: 0 },
};
const WESTERLY: WeatherAtAMoment = parseWeather(WESTERLY_BODY);
// A day warming from 4 °C to 16 °C and back, every six hours.
const DAY_BODY = {
  start: "2025-12-31T23:00:00Z",
  every_s: 21600,
  times_s: [0, 21600, 43200, 64800, 86400],
  weather: [8, 4, 12, 16, 8].map((air_temperature_c) => ({
    ...WESTERLY_BODY.weather,
    air_temperature_c,
  })),
};
const CALM: WeatherAtAMoment = {
  ...WESTERLY,
  weather: { ...WESTERLY.weather, wind_speed_m_s: 0 },
  windMS: { x: 0, y: 0, z: 0 },
};

describe("the weather", () => {
  it("is asked for at a moment of a run, the start left out, under a weather if chosen", () => {
    expect(weatherUrl("climate_box", 0)).toBe("/api/scenarios/climate_box/weather");
    expect(weatherUrl("climate box", 600)).toBe("/api/scenarios/climate%20box/weather?t=600");
    expect(weatherUrl("climate_box", 600, "cold_spring_day")).toBe(
      "/api/scenarios/climate_box/weather?t=600&weather=cold_spring_day",
    );
    expect(weatherDayUrl("climate_box")).toBe("/api/scenarios/climate_box/weather/day");
    expect(weatherDayUrl("climate_box", "cold_spring_day")).toBe(
      "/api/scenarios/climate_box/weather/day?weather=cold_spring_day",
    );
  });

  it("through the day is checked rather than trusted", async () => {
    const answered = (async () => Response.json(DAY_BODY)) as typeof fetch;

    expect(await loadWeatherDay("climate_box", undefined, answered)).toEqual({
      status: "loaded",
      day: parseWeatherDay(DAY_BODY),
    });
    expect(() => parseWeatherDay({ ...DAY_BODY, times_s: [0] })).toThrow(
      "not what the viewer expects",
    );
  });

  it("is checked rather than trusted", () => {
    expect(WESTERLY.windMS).toEqual({ x: 3, y: 0, z: 0 });
    expect(WESTERLY.timeS).toBe(600);
    expect(() => parseWeather({ ...WESTERLY_BODY, weather: { air_temperature_c: 8 } })).toThrow(
      "not what the viewer expects",
    );
    expect(() => parseWeather({ ...WESTERLY_BODY, wind_m_s: null })).toThrow();
  });

  it("is unavailable when the simulator refuses it or cannot be reached", async () => {
    const refused = (async () => new Response("{}", { status: 400 })) as typeof fetch;
    const unreachable = (async () => {
      throw new Error("connection refused");
    }) as typeof fetch;
    const answered = (async () => Response.json(WESTERLY_BODY)) as typeof fetch;

    expect(await loadWeather("climate_box", 0, undefined, refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 400",
    });
    expect(await loadWeather("climate_box", 0, undefined, unreachable)).toEqual({
      status: "unavailable",
      reason: "connection refused",
    });
    expect(await loadWeather("climate_box", 600, "cold_spring_day", answered)).toEqual({
      status: "loaded",
      weather: WESTERLY,
    });
  });

  it("names the point of the compass nearest a bearing", () => {
    expect(compassPoint(0)).toBe("N");
    expect(compassPoint(225)).toBe("SW");
    expect(compassPoint(290)).toBe("WNW");
    expect(compassPoint(355)).toBe("N");
    expect(compassPoint(-90)).toBe("W");
  });

  it("writes the wind by its speed and the point it comes from", () => {
    expect(describeWind(WESTERLY.weather)).toBe("3.0 m/s from the W");
    expect(describeWind(CALM.weather)).toBe("calm");
    // Recorded without a wind vane.
    expect(describeWind({ ...WESTERLY.weather, wind_direction_deg: null })).toBe(
      "3.0 m/s, its direction not known",
    );
    expect(
      parseWeather({
        ...WESTERLY_BODY,
        weather: { ...WESTERLY_BODY.weather, wind_direction_deg: null },
      }).weather.wind_direction_deg,
    ).toBeNull();
  });
});

describe("the wind's arrow", () => {
  it("points along the wind, ending a metre short of the house on the side it comes from", () => {
    const [arrow, label] = windOverlays(EXAMPLE, WESTERLY);

    // The example house is 12 by 6.4 m about (6, 3.2), and 4.8 m high: its
    // corners lie 6.8 m from its middle. Three metres for 3 m/s.
    expect(arrow).toMatchObject({
      id: "wind-arrow",
      kind: "arrow",
      direction: { x: 1, y: 0, z: 0 },
      length: 3,
    });
    if (arrow?.kind === "arrow") {
      expect(arrow.origin.x).toBeCloseTo(6 - 6.8 - 1 - 3);
      expect(arrow.origin.y).toBeCloseTo(3.2);
      expect(arrow.origin.z).toBeCloseTo(2.4);
    }
    expect(label).toMatchObject({ kind: "label", text: "wind 3.0 m/s from the W" });
  });

  it("is longer as the wind blows harder, and turns with it", () => {
    const southWesterly = {
      ...WESTERLY,
      windMS: { x: 4 * Math.SQRT1_2, y: 4 * Math.SQRT1_2, z: 0 },
    };
    const [arrow] = windOverlays(EXAMPLE, southWesterly);

    expect(arrow?.kind).toBe("arrow");
    if (arrow?.kind === "arrow") {
      expect(arrow.length).toBeCloseTo(4);
      expect(arrow.direction.x).toBeCloseTo(Math.SQRT1_2);
      expect(arrow.direction.y).toBeCloseTo(Math.SQRT1_2);
    }
  });

  it("is not drawn in a calm, or without the house", () => {
    expect(windOverlays(EXAMPLE, CALM)).toEqual([]);
    expect(windOverlays({ ...EXAMPLE, entities: [] }, WESTERLY)).toEqual([]);
  });
});

describe("the weather panel", () => {
  const blowing = renderToStaticMarkup(
    <WeatherPanel state={{ status: "loaded", weather: WESTERLY }} />,
  );

  it("shows the moment at the site, in its own time", () => {
    // 23:10 UTC on New Year's Eve is ten past midnight in Amsterdam.
    expect(localTime(WESTERLY)).toBe("1 Jan 2026, 00:10");
  });

  it("shows the outside's air, wind and pressure", () => {
    expect(blowing).toContain(
      'data-testid="weather-summary">Outside at 1 Jan 2026, 00:10: 8.0 °C, wind 3.0 m/s from the W.<',
    );
    expect(blowing).toContain('data-testid="weather-air">8.0 °C, 90% RH, 420 ppm CO₂<');
    expect(blowing).toContain('data-testid="weather-wind">3.0 m/s from the W (270°)<');
    expect(blowing).toContain('data-testid="weather-pressure">1013 hPa<');
  });

  it("turns the compass's needle the way the wind blows, and shows none in a calm", () => {
    const calm = renderToStaticMarkup(<WeatherPanel state={{ status: "loaded", weather: CALM }} />);

    // From the west, it blows east: a quarter turn clockwise from north.
    expect(blowing).toContain('transform="rotate(90 16 16)"');
    expect(calm).not.toContain('data-testid="wind-needle"');
    expect(calm).toContain('data-testid="weather-wind">calm<');
  });

  it("says where the site is, and which way the world's x axis points", () => {
    expect(describeSite(WESTERLY)).toBe("52.00° N, 4.50° E, Europe/Amsterdam; x points E");
  });

  it("says when the weather is on its way or cannot be read", () => {
    expect(renderToStaticMarkup(<WeatherPanel state={{ status: "none" }} />)).toBe("");
    expect(renderToStaticMarkup(<WeatherPanel state={{ status: "loading" }} />)).toContain(
      "Reading the weather…",
    );
    expect(
      renderToStaticMarkup(<WeatherPanel state={{ status: "unavailable", reason: "no API" }} />),
    ).toContain("The weather cannot be read: no API.");
  });
});

describe("choosing a weather", () => {
  const weathers = ["default", "cold_spring_day", "windy_autumn_day"];

  it("names the scenario's own weather and the presets in words", () => {
    expect(weatherName("default")).toBe("its own");
    expect(weatherName("cold_spring_day")).toBe("cold spring day");
  });

  it("offers every weather the scenario can be run under, the chosen one selected", () => {
    const markup = renderToStaticMarkup(
      <WeatherPanel
        state={{ status: "loaded", weather: WESTERLY }}
        weathers={weathers}
        chosen="cold_spring_day"
        onChoose={() => undefined}
      />,
    );

    expect(markup).toContain('aria-label="Weather to run under"');
    expect(markup).toContain('<option value="default">its own</option>');
    expect(markup).toContain(
      '<option value="cold_spring_day" selected="">cold spring day</option>',
    );
  });

  it("offers no choice where there is none to make", () => {
    const markup = renderToStaticMarkup(
      <WeatherPanel state={{ status: "loaded", weather: WESTERLY }} weathers={["default"]} />,
    );

    expect(markup).not.toContain("Weather to run under");
  });
});

describe("the day's weather", () => {
  const day = parseWeatherDay(DAY_BODY);

  it("charts the air, its humidity and the wind from their least to their most", () => {
    const markup = renderToStaticMarkup(
      <WeatherDayChart state={{ status: "loaded", day }} time={21600} />,
    );

    expect(markup).toContain('data-testid="weather-day-day-temperature">Air, 4.0 to 16.0 °C<');
    // Humidity and wind hold all day here: flat, at one value.
    expect(markup).toContain('data-testid="weather-day-day-humidity">Humidity, 90.0 %<');
    expect(markup).toContain('data-testid="weather-day-day-wind">Wind, 3.0 m/s<');
    // The coldest at six hours in, at the foot of its chart.
    expect(markup).toContain('points="0.0,18.7 60.0,28.0 120.0,9.3 180.0,0.0 240.0,18.7"');
  });

  it("marks the moment drawn across each chart", () => {
    const markup = renderToStaticMarkup(
      <WeatherDayChart state={{ status: "loaded", day }} time={21600} />,
    );

    expect(markup.match(/data-testid="weather-day-now" x1="60" x2="60"/g)).toHaveLength(3);
  });

  it("says when it is on its way or cannot be read", () => {
    expect(renderToStaticMarkup(<WeatherDayChart state={{ status: "none" }} time={0} />)).toBe("");
    expect(
      renderToStaticMarkup(
        <WeatherDayChart state={{ status: "unavailable", reason: "no API" }} time={0} />,
      ),
    ).toContain("weather cannot be read: no API.");
  });
});
