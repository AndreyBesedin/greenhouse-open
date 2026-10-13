import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { glazingUrl } from "../fields/glazing";
import { houseAirUrl } from "../fields/HouseAir";
import { openingsUrl } from "../fields/openingFlows";
import { probeChartsUrl } from "../fields/ProbeCharts";
import { CLIMATE_FIELD, fieldUrl } from "../fields/source";
import { cropPlantUrl, cropUrl } from "../plants/crop";
import { plantsLightUrl } from "../plants/light";
import { sensorsUrl } from "../sensors/readings";
import { weatherDayUrl, weatherUrl } from "../weather/weather";
import { runApartFromItsMoment, runParameters, runsSomething, scenarioRun } from "./run";
import { sourceFromSearch } from "./source";

function runOf(search: string) {
  const source = sourceFromSearch(search);
  if (source.kind !== "scenario") {
    throw new Error(`${search} is not a scenario's address`);
  }
  return scenarioRun(source);
}

describe("a scenario's run, as the viewer asks for it", () => {
  it("is its address's parts, with its weather's clouds as the API names them", () => {
    expect(
      runOf(
        "?scenario=solar_lab&layout=open&field=climate&t=600&set=heater:1&open=roof_vent:0.5&schedule=300:heater:0&clouds=80",
      ),
    ).toEqual({
      scenarioId: "solar_lab",
      layout: "open",
      levels: { heater: 1 },
      openings: { roof_vent: 0.5 },
      schedule: [{ timeS: 300, actuatorId: "heater", level: 0 }],
      time: 600,
      weather: "default@80",
    });
    expect(runOf("?scenario=climate_box&weather=cold_spring_day").weather).toBe("cold_spring_day");
  });

  it("asks for every part of a climate run under the clouds and the layout drawn", () => {
    const run = runOf("?scenario=solar_lab&layout=open&field=climate&t=46200&clouds=100");
    const id = run.scenarioId;
    const asked = [
      fieldUrl(id, CLIMATE_FIELD, run),
      houseAirUrl(id, run),
      glazingUrl(id, run),
      openingsUrl(id, run),
      probeChartsUrl(id, { ...run, probes: [{ x: 1, y: 2, z: 0.75 }] }),
      sensorsUrl(id, "observations", run),
      sensorsUrl(id, "truth", run),
      plantsLightUrl(id, run),
      cropUrl({ ...run, time: 2 * DAY_S + 46200 }),
      cropPlantUrl({ ...run, time: 2 * DAY_S + 46200 }, "solar_lab_plant_001"),
    ];
    for (const url of asked) {
      expect(url).toContain("layout=open");
      expect(url).toMatch(/t=(46200|172800)(&|$)/);
      expect(url).toContain("weather=default%40100");
    }
    // The weather does not depend on the layout.
    expect(weatherUrl(id, 46200, run.weather)).toBe(
      "/api/scenarios/solar_lab/weather?t=46200&weather=default%40100",
    );
    expect(weatherDayUrl(id, 46200, run.weather)).toBe(
      "/api/scenarios/solar_lab/weather/day?weather=default%40100",
    );
  });

  it("writes its parts in the API's order, only those asked for, and not its start", () => {
    const run = runOf(
      "?scenario=climate_box&layout=open&field=climate&t=0&set=fan:1&schedule=60:fan:0&weather=hot_day",
    );

    expect(runParameters(run)).toEqual([
      "layout=open",
      "set=fan:1",
      "schedule=60:fan:0",
      "weather=hot_day",
    ]);
    expect(runParameters(run, ["layout"])).toEqual(["layout=open"]);
    expect(runParameters({ time: 600 }, ["time"])).toEqual(["t=600"]);
  });

  it("is the same run at another moment, but not under other clouds", () => {
    const at = (search: string) => runApartFromItsMoment(runOf(search));

    expect(at("?scenario=climate_box&field=climate&t=600")).toBe(
      at("?scenario=climate_box&field=climate&t=1200"),
    );
    expect(at("?scenario=climate_box&field=climate&t=600")).not.toBe(
      at("?scenario=climate_box&field=climate&t=600&clouds=50"),
    );
  });

  it("runs something when its equipment is set, or commanded after the start", () => {
    expect(runsSomething(runOf("?scenario=climate_box&field=climate"))).toBe(false);
    expect(runsSomething(runOf("?scenario=climate_box&field=climate&set=fan:1"))).toBe(true);
    expect(runsSomething(runOf("?scenario=climate_box&field=climate&schedule=60:fan:1"))).toBe(
      true,
    );
  });
});
