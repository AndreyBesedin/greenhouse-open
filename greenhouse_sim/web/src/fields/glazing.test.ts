import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { colouringBy, scalarProperties } from "../debug/scalar";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  GLASS_LOSS,
  glazingUrl,
  loadGlazing,
  parseGlazing,
  SURFACE_TEMPERATURE,
  withGlazing,
} from "./glazing";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
// The climate box heated, ten minutes in: its back wall, by the heater, the
// warmest glass.
const BODY = {
  time_s: 600,
  outside_c: 8,
  u_w_m2k: 3.4,
  surfaces: [
    { surface_id: "end_wall_back", air_c: 27.39, surface_c: 19.641, loss_w: 1688.4 },
    { surface_id: "end_wall_front", air_c: 14.77, surface_c: 12.059, loss_w: 589.2 },
  ],
};

describe("the glazing", () => {
  it("is asked for as the climate is, at the moment drawn", () => {
    expect(glazingUrl("climate_box", { levels: { heater: 1 }, time: 600 })).toBe(
      "/api/scenarios/climate_box/climate/glazing?set=heater:1&t=600",
    );
  });

  it("is checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;

    expect(await loadGlazing("/x", answered)).toEqual({ status: "loaded", glazing: BODY });
    expect(() => parseGlazing({ ...BODY, surfaces: [{ surface_id: "x" }] })).toThrow(
      "not what the viewer expects",
    );
  });

  it("gives each glazed surface's entity its temperature and loss, to colour by", () => {
    const glazed = withGlazing(EXAMPLE, parseGlazing(BODY));
    const back = glazed.entities.find((e) => e.entity_id === "climate_box_end_wall_back");
    const floor = glazed.entities.find((e) => e.entity_id === "climate_box_floor");

    expect(back?.properties[SURFACE_TEMPERATURE]).toBe(19.64);
    expect(back?.properties[GLASS_LOSS]).toBe(1688);
    expect(floor?.properties[SURFACE_TEMPERATURE]).toBeUndefined();
    expect(scalarProperties(glazed)).toContain(SURFACE_TEMPERATURE);
    expect(colouringBy(glazed, SURFACE_TEMPERATURE)?.range).toEqual({ min: 12.06, max: 19.64 });
    // The scene it was given is left as it was.
    expect(scalarProperties(EXAMPLE)).not.toContain(SURFACE_TEMPERATURE);
  });
});
