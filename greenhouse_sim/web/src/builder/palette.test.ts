import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { hosts, hostsFor, startingCentre } from "./palette";

const SCENE = {
  greenhouse_id: "house",
  entities: [
    { entity_id: "house_floor", kind: "FLOOR", shape: { shape: "plane", size_x: 12, size_y: 6 } },
    {
      entity_id: "house_roof_1_right",
      kind: "ROOF",
      shape: { shape: "plane", size_x: 12, size_y: 2 },
    },
    {
      entity_id: "house_end_wall_front",
      kind: "WALL",
      shape: {
        shape: "polygon",
        points: [
          { x: 0, y: 0 },
          { x: 6, y: 0 },
          { x: 6, y: 4 },
          { x: 3, y: 4.5 },
          { x: 0, y: 4 },
        ],
      },
    },
    { entity_id: "house_heater_1", kind: "HEATER", shape: { shape: "box" } },
  ],
} as unknown as SceneSnapshot;

describe("the builder's palette (P12.3)", () => {
  it("finds the walls and roof slopes a door or vent goes on, and how far each reaches", () => {
    expect(hosts(SCENE)).toEqual([
      { surfaceId: "roof_1_right", category: "roof", low: { x: -6, y: -1 }, high: { x: 6, y: 1 } },
      {
        surfaceId: "end_wall_front",
        category: "wall",
        low: { x: 0, y: 0 },
        high: { x: 6, y: 4.5 },
      },
    ]);
  });

  it("puts a roof vent on the roof, a door or a side vent on a wall", () => {
    const all = hosts(SCENE);

    expect(hostsFor("roof_vent", all).map((host) => host.surfaceId)).toEqual(["roof_1_right"]);
    expect(hostsFor("door", all).map((host) => host.surfaceId)).toEqual(["end_wall_front"]);
  });

  it("first puts a door on the floor halfway along, a vent halfway up", () => {
    const [roof, wall] = hosts(SCENE);
    if (roof === undefined || wall === undefined) {
      throw new Error("no hosts");
    }

    expect(startingCentre("door", 2, wall)).toEqual({ x: 3, y: 1 });
    expect(startingCentre("roof_vent", 0.6, roof)).toEqual({ x: 0, y: 0 });
  });
});
