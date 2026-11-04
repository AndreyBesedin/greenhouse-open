import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  describeHouseAir,
  HouseAir,
  houseAirOnShow,
  houseAirUrl,
  loadHouseAir,
  ownHouseAirUrl,
  parseHouseAir,
  withAllOff,
} from "./HouseAir";

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

  it("is asked for apart from the same run all off", () => {
    expect(ownHouseAirUrl("climate_box", { time: 600 })).toBe(
      "/api/scenarios/climate_box/climate/house?t=600&all_off=0",
    );
    expect(ownHouseAirUrl("climate_box", {})).toBe(
      "/api/scenarios/climate_box/climate/house?all_off=0",
    );
  });

  it("charts the run's own air while the run all off is on its way", () => {
    const own = { status: "loaded" as const, trace: { ...BODY, all_off: null } };
    const html = renderToStaticMarkup(<HouseAir state={own} />);

    expect(html).toContain("Air 15.6 °C, all off on its way");
    expect(html).not.toContain("house-air-off");
    expect(describeHouseAir(own)).toBe("House air: 15.6 °C, 85.0 %, 420.0 ppm");
  });

  it("takes the run all off from an answer of the same day, as far as it reaches", () => {
    const own = { status: "loaded" as const, trace: { ...BODY, all_off: null } };
    const whole = { status: "loaded" as const, trace: BODY };
    expect(withAllOff(own, null)).toBe(own);
    expect(withAllOff(own, whole)).toEqual(whole);

    const earlier = {
      status: "loaded" as const,
      trace: {
        times_s: [0, 60],
        controlled: SERIES([16, 15.8]),
        all_off: SERIES([16, 15.2]),
      },
    };
    const html = renderToStaticMarkup(<HouseAir state={withAllOff(own, earlier)} />);
    expect(html).toContain("all off on its way");
    expect(html).toContain("house-air-off");

    const anotherDay = {
      status: "loaded" as const,
      trace: { ...BODY, times_s: [86_400, 86_460, 86_520] },
    };
    expect(withAllOff(own, anotherDay)).toBe(own);
    const loading = { status: "loading" as const };
    expect(withAllOff(loading, whole)).toBe(loading);
  });

  it("matches the run all off to the run's own moments, not to how many there are", () => {
    const series = SERIES([16, 15.8, 15.6]);
    // Both end between minutes, at another moment each, with as many samples.
    const own = {
      status: "loaded" as const,
      trace: { times_s: [0, 60, 119], controlled: series, all_off: null },
    };
    const whole = {
      status: "loaded" as const,
      trace: { times_s: [0, 60, 61], controlled: series, all_off: SERIES([16, 15.2, 15.1]) },
    };
    const merged = withAllOff(own, whole);

    const html = renderToStaticMarkup(<HouseAir state={merged} />);
    expect(html).toContain("Air 15.6 °C, all off on its way");
    expect(html).not.toContain("all off 15.1");
    expect(merged.status === "loaded" && merged.trace.all_off?.temperature_c).toEqual([16, 15.2]);
  });

  it("takes as far as the run's own moments from an answer that reaches further", () => {
    const own = { status: "loaded" as const, trace: { ...BODY, all_off: null } };
    const further = {
      status: "loaded" as const,
      trace: {
        times_s: [0, 60, 120, 180],
        controlled: SERIES([16, 15.8, 15.6, 15.4]),
        all_off: SERIES([16, 15.2, 14.5, 13.9]),
      },
    };

    expect(withAllOff(own, further)).toEqual({ status: "loaded", trace: BODY });
  });

  it("reads an answer without the run all off", async () => {
    const without = { ...BODY, all_off: null };
    const answered = (async () => Response.json(without)) as typeof fetch;

    expect(await loadHouseAir("/x", answered)).toEqual({ status: "loaded", trace: without });
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

  it("says in a line, folded, where the run's air has reached (#273)", () => {
    expect(describeHouseAir({ status: "loaded", trace: parseHouseAir(BODY) })).toBe(
      "House air: 15.6 °C, 85.0 %, 420.0 ppm",
    );
    expect(describeHouseAir({ status: "loading" })).toBe("House air: mixing…");
    expect(describeHouseAir({ status: "unavailable", reason: "no" })).toBe(
      "House air: cannot be read",
    );
  });

  it("says that what it shows is of an earlier moment while the next is on its way", () => {
    const shown = { status: "loaded", trace: parseHouseAir(BODY) } as const;

    expect(describeHouseAir(houseAirOnShow({ shown, latest: { status: "loading" } }))).toBe(
      "House air: 15.6 °C, 85.0 %, 420.0 ppm; mixing…",
    );
    // Its own answer says nothing more, and one that failed says that.
    expect(describeHouseAir(houseAirOnShow({ shown, latest: shown }))).toBe(
      "House air: 15.6 °C, 85.0 %, 420.0 ppm",
    );
    expect(
      describeHouseAir(houseAirOnShow({ shown, latest: { status: "unavailable", reason: "no" } })),
    ).toBe("House air: cannot be read");
    // With nothing yet to show, it is only on its way.
    expect(describeHouseAir(houseAirOnShow({ shown: null, latest: { status: "loading" } }))).toBe(
      "House air: mixing…",
    );
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

  it("charts a later day across that day, from its midnight", () => {
    const day = 86_400;
    const markup = renderToStaticMarkup(
      <HouseAir
        state={{
          status: "loaded",
          trace: parseHouseAir({ ...BODY, times_s: [day, day + 21_600, day + 43_200] }),
        }}
      />,
    );

    // Its first moment at the chart's left, a quarter and a half across after it.
    expect(markup).toContain('class="house-air-run" points="0.0,0.0 60.0,3.7 120.0,7.5"');
  });

  it("says when it is on its way or cannot be read", () => {
    expect(renderToStaticMarkup(<HouseAir state={{ status: "none" }} />)).toBe("");
    expect(renderToStaticMarkup(<HouseAir state={{ status: "loading" }} />)).toContain(
      "Mixing the house",
    );
  });
});
