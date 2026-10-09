import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { scalarProperties } from "../debug/scalar";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  describeFlow,
  loadOpenings,
  NET_FLOW,
  openingFlowOverlays,
  openingsUrl,
  parseOpenings,
  withOpeningFlows,
} from "./openingFlows";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
// A southerly across the climate box: in at the right side vent, at y = 0,
// out at the left, at y = 6.4.
const BODY = {
  time_s: 600,
  openings: [
    { opening_id: "side_vent", net_m3_s: 2, exchange_m3_s: 0.14 },
    { opening_id: "side_vent_left", net_m3_s: -2, exchange_m3_s: 0.14 },
  ],
};

describe("the openings' flows", () => {
  it("are asked for as the climate is, at the moment drawn", () => {
    expect(
      openingsUrl("climate_box", {
        openings: { side_vent: 1 },
        time: 600,
        weather: "cold_spring_day",
      }),
    ).toBe(
      "/api/scenarios/climate_box/climate/openings?open=side_vent:1&t=600&weather=cold_spring_day",
    );
  });

  it("are checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;

    expect(await loadOpenings("/x", answered)).toEqual({ status: "loaded", openings: BODY });
    expect(() => parseOpenings({ time_s: 0, openings: [{ opening_id: "x" }] })).toThrow(
      "not what the viewer expects",
    );
  });

  it("give each opening's entity its flow, to colour by", () => {
    const flowing = withOpeningFlows(EXAMPLE, parseOpenings(BODY));
    const left = flowing.entities.find((e) => e.entity_id === "climate_box_side_vent_left");

    expect(left?.properties[NET_FLOW]).toBe(-2);
    expect(scalarProperties(flowing)).toContain(NET_FLOW);
  });

  it("are drawn as arrows in where air enters and out where it leaves", () => {
    const [into, intoLabel, out] = openingFlowOverlays(EXAMPLE, parseOpenings(BODY));

    expect(into).toMatchObject({ kind: "arrow", length: 2 });
    if (into?.kind === "arrow" && out?.kind === "arrow") {
      // From outside the right wall, pointing in along +y.
      expect(into.origin.y).toBeCloseTo(-2.2);
      expect(into.direction.y).toBeCloseTo(1);
      // From inside the left wall, pointing out along +y.
      expect(out.origin.y).toBeCloseTo(6.4 - 2.2);
      expect(out.direction.y).toBeCloseTo(1);
    }
    expect(intoLabel).toMatchObject({ kind: "label", text: "2.00 m³/s in" });
    expect(describeFlow(-0.5)).toBe("0.50 m³/s out");
  });

  it("draw nothing where nothing passes net", () => {
    const still = {
      time_s: 0,
      openings: [{ opening_id: "side_vent", net_m3_s: 0, exchange_m3_s: 0.1 }],
    };

    expect(openingFlowOverlays(EXAMPLE, still)).toEqual([]);
  });
});
