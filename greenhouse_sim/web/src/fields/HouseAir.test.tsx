import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HouseAir, houseAirUrl, loadHouseAir, parseHouseAir } from "./HouseAir";

const SERIES = (temperature: number[]) => ({
  temperature_c: temperature,
  humidity_pct: temperature.map(() => 85),
  co2_ppm: temperature.map(() => 420),
  removed_kg: temperature.map(() => 0),
  condensed_kg: temperature.map(() => 0),
});
// A heated house and the same one all off, over its first two minutes.
const BODY = {
  times_s: [0, 60, 120],
  controlled: SERIES([16, 15.8, 15.6]),
  all_off: SERIES([16, 15.2, 14.5]),
};

describe("the house's air", () => {
  it("is asked for as the climate is, up to the moment drawn", () => {
    expect(
      houseAirUrl("climate_box", {
        levels: { heater: 1 },
        openings: { roof_vent: 1 },
        time: 600,
        weather: "cold_spring_day",
      }),
    ).toBe(
      "/api/scenarios/climate_box/climate/house?set=heater:1&open=roof_vent:1&t=600&weather=cold_spring_day",
    );
    expect(houseAirUrl("climate_box", {})).toBe("/api/scenarios/climate_box/climate/house");
  });

  it("is checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;
    const refused = (async () => new Response("{}", { status: 404 })) as typeof fetch;

    expect(await loadHouseAir("/x", answered)).toEqual({ status: "loaded", trace: BODY });
    expect(await loadHouseAir("/x", refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 404",
    });
    expect(() => parseHouseAir({ ...BODY, times_s: [0, 60] })).toThrow("not what the viewer");
  });

  it("charts the run beside the same run all off, saying where each has reached", () => {
    const markup = renderToStaticMarkup(
      <HouseAir state={{ status: "loaded", trace: parseHouseAir(BODY) }} />,
    );

    expect(markup).toContain('data-testid="house-air-°C">Air 15.6 °C, all off 14.5 °C<');
    expect(markup).toContain('data-testid="house-air-ppm">CO₂ 420.0 ppm, all off 420.0 ppm<');
    expect(markup.match(/class="house-air-off"/g)).toHaveLength(3);
    expect(markup.match(/class="house-air-run"/g)).toHaveLength(3);
  });

  it("says when it is on its way or cannot be read", () => {
    expect(renderToStaticMarkup(<HouseAir state={{ status: "none" }} />)).toBe("");
    expect(renderToStaticMarkup(<HouseAir state={{ status: "loading" }} />)).toContain(
      "Mixing the house",
    );
  });
});
