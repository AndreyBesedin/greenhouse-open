import Ajv2020 from "ajv/dist/2020";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Installation } from "./generated/assessedTypes";
import { EDIT_SCHEMA } from "./generated/editSchema";
import {
  drawnAs,
  FIXTURE_KINDS,
  hosts,
  hostsFor,
  ITEM_KINDS,
  itemOf,
  listed,
  startingCentre,
  startingPlace,
} from "./palette";

// A house with a zone, a walkway, a pipe run and a rail, as its file has
// them.
const HOUSE = {
  layout: {
    zones: [
      {
        zone_id: "service_1",
        kind: "service",
        area: { start: { x: 11, y: 0.5 }, end: { x: 11, y: 1.5 }, width: 0.8 },
        height: 2,
      },
    ],
    placed: [
      {
        primitive: "walkway",
        fixture_id: "path_1",
        start: { x: 2, y: 0.3 },
        end: { x: 2, y: 5.7 },
        width: 0.8,
      },
      {
        primitive: "pipe_run",
        fixture_id: "heating_1",
        start: { x: 0.5, y: 1, z: 0.1 },
        end: { x: 11.5, y: 1, z: 0.1 },
        radius: 0.03,
        count: 2,
        step: { x: 0, y: 0.2, z: 0 },
      },
      {
        primitive: "rail",
        fixture_id: "rail_1",
        start: { x: 0.5, y: 3, z: 0.1 },
        end: { x: 11.5, y: 3, z: 0.1 },
        gauge: 0.55,
        tube_radius: 0.025,
      },
    ],
  },
  envelope: {},
} as unknown as Installation;

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

  it("places each kind as the simulator takes it", () => {
    // An edit's schema tells its kinds apart by a discriminator's mapping,
    // which Ajv does not read: each kind's constant does it as well.
    const valid = new Ajv2020({ strict: false, validateFormats: false }).compile(EDIT_SCHEMA);

    for (const kind of [...ITEM_KINDS, ...FIXTURE_KINDS]) {
      const edit = { edit: "place_items", item: itemOf(kind, startingPlace(kind)) };
      expect([kind, valid(edit), valid.errors ?? []]).toEqual([kind, true, []]);
    }
  });

  it("lists zones and fixtures with their kind and where they lie", () => {
    expect(listed(HOUSE)).toEqual([
      { id: "service_1", kind: "service_zone", where: "11 m, 0.5 m to 11 m, 1.5 m", on: "house" },
      { id: "path_1", kind: "walkway", where: "2 m, 0.3 m to 2 m, 5.7 m", on: "house" },
      {
        id: "heating_1",
        kind: "pipe_run",
        where: "0.5 m, 1 m, 0.1 m to 11.5 m, 1 m, 0.1 m",
        on: "house",
      },
      { id: "rail_1", kind: "rail", where: "0.5 m, 3 m, 0.1 m to 11.5 m, 3 m, 0.1 m", on: "house" },
    ]);
  });

  it("knows a pipe run by its pipes and a rail by its tubes, as the simulator names them", () => {
    expect(Object.fromEntries(drawnAs(HOUSE))).toEqual({
      service_1: ["service_1"],
      path_1: ["path_1"],
      heating_1: ["heating_1_1", "heating_1_2"],
      rail_1: ["rail_1_right", "rail_1_left"],
    });
  });
});
