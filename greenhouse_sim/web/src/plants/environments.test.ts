import { describe, expect, it } from "vitest";

import { describeEnvironment, labEnvironments, loadLabEnvironments } from "./environments";

// Two of the lab's environments, as the simulator writes them.
const ENVIRONMENTS = {
  reference: { mean_temperature_c: 21, par_mol_m2_day: 25, co2_ppm: 800, water_status: 1 },
  dry: { mean_temperature_c: 21, par_mol_m2_day: 25, co2_ppm: 800, water_status: 0.5 },
};

const DRY = { meanTemperatureC: 21, parMolM2Day: 25, co2Ppm: 800, waterStatus: 0.5 };

describe("the plant lab's environments", () => {
  it("are read by name, and described in words", () => {
    const read = labEnvironments(ENVIRONMENTS);

    expect(Object.keys(read)).toEqual(["reference", "dry"]);
    expect(read.dry).toEqual(DRY);
    expect(describeEnvironment(DRY)).toBe("21 °C, 25 mol/m²/d PAR, 800 ppm CO₂, water 50%");
  });

  it("refuse what they cannot read", () => {
    expect(() => labEnvironments([])).toThrow("not an object");
    expect(() => labEnvironments({ dry: { ...ENVIRONMENTS.dry, co2_ppm: "high" } })).toThrow(
      "dry's co2_ppm is not a number",
    );
  });

  it("are loaded from the lab, and an error becomes unavailable", async () => {
    const loaded = await loadLabEnvironments(
      async () => new Response(JSON.stringify(ENVIRONMENTS), { status: 200 }),
    );
    const refused = await loadLabEnvironments(async () => new Response("{}", { status: 500 }));

    expect(loaded.status).toBe("loaded");
    expect(refused).toEqual({ status: "unavailable", reason: "the simulator API answered 500" });
  });
});
