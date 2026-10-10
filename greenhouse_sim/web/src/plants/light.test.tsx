import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { describePlantLight, loadPlantsLight, parsePlantsLight, plantsLightUrl } from "./light";
import { PlantLight } from "./PlantLight";

// The light on two plants an hour before noon, one behind the crates.
const BODY = {
  time_s: 42600,
  par_umol_m2_s: { solar_lab_plant_001: 0, solar_lab_plant_016: 1049.04 },
  daily_light_integral_mol_m2_d: { solar_lab_plant_001: 7.05, solar_lab_plant_016: 27.27 },
};

describe("the plants' light", () => {
  it("is asked for at a moment, under a weather and with a layout", () => {
    expect(plantsLightUrl("solar_lab", 0)).toBe("/api/scenarios/solar_lab/climate/plants");
    expect(plantsLightUrl("solar_lab", 42600, "hot_dry_summer_day", "benches")).toBe(
      "/api/scenarios/solar_lab/climate/plants?layout=benches&t=42600&weather=hot_dry_summer_day",
    );
  });

  it("is checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;

    expect(await loadPlantsLight("solar_lab", 42600, undefined, undefined, answered)).toEqual({
      status: "loaded",
      light: parsePlantsLight(BODY),
    });
    expect(() => parsePlantsLight({ ...BODY, par_umol_m2_s: { a: "bright" } })).toThrow(
      "not what the viewer expects",
    );
    const refused = (async () => new Response("{}", { status: 400 })) as typeof fetch;
    expect(await loadPlantsLight("solar_lab", 90000, undefined, undefined, refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 400",
    });
  });

  it("is written as the moment's PAR and the day's light", () => {
    const light = parsePlantsLight(BODY);

    expect(describePlantLight(light, "solar_lab_plant_016")).toEqual({
      now: "1049 µmol/m²/s",
      day: "27.3 mol/m²/d",
    });
    expect(describePlantLight(light, "nobody")).toBeNull();
  });

  it("is shown for the plant selected, or why it is not", () => {
    const light = parsePlantsLight(BODY);
    const shaded = renderToStaticMarkup(
      <PlantLight plantId="solar_lab_plant_001" state={{ status: "loaded", light }} />,
    );

    expect(shaded).toContain('data-testid="plant-par">0 µmol/m²/s<');
    expect(shaded).toContain('data-testid="plant-daily-light">7.0 mol/m²/d<');
    expect(renderToStaticMarkup(<PlantLight plantId="x" state={{ status: "none" }} />)).toBe("");
    expect(
      renderToStaticMarkup(
        <PlantLight plantId="x" state={{ status: "unavailable", reason: "no API" }} />,
      ),
    ).toContain("cannot be read: no API.");
  });
});
