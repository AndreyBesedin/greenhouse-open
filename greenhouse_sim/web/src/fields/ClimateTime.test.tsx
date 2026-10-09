import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { searchFor, sourceFromSearch } from "../scene/source";
import { ClimateTime, describeTime, playStep } from "./ClimateTime";
import { CLIMATE_RUN_S, fieldUrl } from "./source";

const ignore = () => undefined;

describe("a climate run's moment", () => {
  it("is written in minutes, and in hours and minutes after the first hour", () => {
    expect(describeTime(0)).toBe("0 min");
    expect(describeTime(600)).toBe("10 min");
    expect(describeTime(90)).toBe("1.5 min");
    expect(describeTime(3600)).toBe("1 h 00 min");
    expect(describeTime(5 * 3600 + 300)).toBe("5 h 05 min");
    expect(describeTime(86_400)).toBe("24 h 00 min");
  });

  it("plays a minute at a time through the first hour, and five after it", () => {
    expect(playStep(600)).toBe(60);
    expect(playStep(3600)).toBe(300);
  });

  it("is chosen on a slider over the run, a minute at a time, and played", () => {
    const html = renderToStaticMarkup(
      <ClimateTime time={600} shown={540} playing={false} onTime={ignore} onPlaying={ignore} />,
    );

    expect(html).toContain('aria-label="Climate run"');
    expect(html).toContain(
      `type="range" aria-label="Time into the run" min="0" max="${CLIMATE_RUN_S}" step="60" value="600"`,
    );
    // Until the moment asked for arrives, the one drawn is shown.
    expect(html).toContain('data-testid="climate-time">9 min<');
    expect(html).toContain(">Play</button>");
  });

  it("is kept in the address with the field, and asked of the climate alone", () => {
    const source = sourceFromSearch("?scenario=climate_box&field=climate&t=600&set=heater:1");

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
      time: 600,
      levels: { heater: 1 },
    });
    expect(searchFor(source)).toBe("?scenario=climate_box&set=heater:1&field=climate&t=600");
    expect(sourceFromSearch("?scenario=climate_box&t=600")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
    });
    expect(sourceFromSearch("?scenario=climate_box&field=climate&t=-5")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
    });
    expect(fieldUrl("climate_box", "climate", { time: 600 })).toBe(
      "/api/scenarios/climate_box/fields/climate?t=600",
    );
    expect(fieldUrl("climate_box", "climate", { time: 0 })).toBe(
      "/api/scenarios/climate_box/fields/climate",
    );
    expect(fieldUrl("climate_box", "shear", { time: 600 })).toBe(
      "/api/scenarios/climate_box/fields/shear",
    );
    // Under another weather, which only its climate depends on.
    expect(fieldUrl("climate_box", "climate", { time: 600, weather: "cold_spring_day" })).toBe(
      "/api/scenarios/climate_box/fields/climate?t=600&weather=cold_spring_day",
    );
    expect(fieldUrl("climate_box", "uniform", { weather: "cold_spring_day" })).toBe(
      "/api/scenarios/climate_box/fields/uniform",
    );
  });
});
