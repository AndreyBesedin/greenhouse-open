/**
 * What the builder places from its palette (P12.3): a piece of equipment,
 * a sensor, a door or a vent of each kind, at the sizes a greenhouse
 * usually has them, to change before it is placed; the surfaces of the
 * house a door or vent goes on, as the simulator draws them; and the items
 * an installation has, to choose among. The edits themselves are the
 * simulator's (`builder.items`): the builder only says which.
 */

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Installation } from "./generated/assessedTypes";
import type { Equipment, Opening, Point2, Sensor, Vector3 } from "./generated/editTypes";

/** What the palette places inside the house. */
export type ItemKind = "fan" | "heater" | "dehumidifier" | "temperature" | "humidity" | "co2";

/** What the palette places on a surface. */
export type OpeningKind = Opening["kind"];

export const ITEM_KINDS: readonly ItemKind[] = [
  "fan",
  "heater",
  "dehumidifier",
  "temperature",
  "humidity",
  "co2",
];
export const OPENING_KINDS: readonly OpeningKind[] = ["roof_vent", "side_vent", "door"];

/** A surface a door or vent goes on: its identifier, whether it is a wall
 * or a roof, and how far it reaches in its own plane, in metres, where an
 * opening's centre is given. */
export interface Host {
  surfaceId: string;
  category: "wall" | "roof";
  low: Point2;
  high: Point2;
}

/** The walls and roof slopes of the house a scene draws, in its order. */
export function hosts(snapshot: SceneSnapshot): Host[] {
  const prefix = `${snapshot.greenhouse_id}_`;
  return snapshot.entities.flatMap((entity): Host[] => {
    const { kind, shape } = entity;
    if ((kind !== "WALL" && kind !== "ROOF") || !entity.entity_id.startsWith(prefix)) {
      return [];
    }
    const points =
      shape.shape === "plane"
        ? [
            { x: -shape.size_x / 2, y: -shape.size_y / 2 },
            { x: shape.size_x / 2, y: shape.size_y / 2 },
          ]
        : shape.shape === "polygon"
          ? shape.points
          : [];
    if (points.length === 0) {
      return [];
    }
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    return [
      {
        surfaceId: entity.entity_id.slice(prefix.length),
        category: kind === "WALL" ? "wall" : "roof",
        low: { x: Math.min(...xs), y: Math.min(...ys) },
        high: { x: Math.max(...xs), y: Math.max(...ys) },
      },
    ];
  });
}

/** The surfaces an opening of `kind` goes on: a roof vent on the roof's
 * slopes, a side vent or a door on the walls. */
export function hostsFor(kind: OpeningKind, all: readonly Host[]): Host[] {
  const category = kind === "roof_vent" ? "roof" : "wall";
  return all.filter((host) => host.category === category);
}

/** A piece of equipment or a sensor of `kind`, named after it, standing at
 * `at`: a fan's centre, a unit's base, a sensor's position. */
export function itemOf(kind: ItemKind, at: Vector3): Equipment | Sensor {
  switch (kind) {
    case "fan":
      return { actuator_id: "fan", kind, position: at, diameter_m: 0.5, flow_m3_s: 1.0 };
    case "heater":
      return {
        actuator_id: "heater",
        kind,
        base: at,
        size_x: 0.6,
        size_y: 0.8,
        size_z: 1.2,
        power_w: 10_000,
      };
    case "dehumidifier":
      return {
        actuator_id: "dehumidifier",
        kind,
        base: at,
        size_x: 0.6,
        size_y: 1.0,
        size_z: 1.4,
        removal_kg_h: 1.0,
        heat_w: 1_200,
      };
    default:
      return { sensor_id: kind, kind, position: at };
  }
}

/** How high each kind first stands: a fan near the roof, a sensor at a
 * plant's height, a unit on the floor. */
const STARTING_HEIGHTS: Readonly<Record<ItemKind, number>> = {
  fan: 3.0,
  heater: 0,
  dehumidifier: 0,
  temperature: 1.5,
  humidity: 1.5,
  co2: 1.5,
};

/** Where the palette first places a `kind` inside the house, a metre in
 * from its corner. */
export function startingPlace(kind: ItemKind): Vector3 {
  return { x: 1.0, y: 1.0, z: STARTING_HEIGHTS[kind] };
}

/** Each opening's usual size, in metres: a door a person walks through, a
 * roof vent and a side vent as greenhouses have them. */
const OPENING_SIZES: Readonly<Record<OpeningKind, { width: number; height: number }>> = {
  door: { width: 1.2, height: 2.1 },
  roof_vent: { width: 1.0, height: 0.6 },
  side_vent: { width: 2.0, height: 0.8 },
};

/** A door or vent of `kind`, named after it, at its usual size. */
export function openingOf(kind: OpeningKind, surfaceId: string, centre: Point2): Opening {
  return { opening_id: kind, kind, surface_id: surfaceId, centre, ...OPENING_SIZES[kind] };
}

/** Where a door or vent of `height` first goes on `host`: halfway along
 * it; a door on the floor, a vent halfway up. */
export function startingCentre(kind: OpeningKind, height: number, host: Host): Point2 {
  const x = (host.low.x + host.high.x) / 2;
  const y = kind === "door" ? host.low.y + height / 2 : (host.low.y + host.high.y) / 2;
  return { x, y };
}

/** An item an installation has, as the builder lists it to choose. */
export interface Listed {
  id: string;
  /** What it is: its kind. */
  kind: string;
  /** Where it is, in words. */
  where: string;
  /** Equipment and sensors are placed in the house, doors and vents on a
   * surface: an edit acts on one or the other. */
  on: "house" | "surface";
}

const metres = (value: number) => `${Number(value.toFixed(2))} m`;
const point = ({ x, y, z }: Vector3) => `${metres(x)}, ${metres(y)}, ${metres(z)}`;

/** The installation's equipment, sensors, doors and vents, in its order. */
export function listed(installation: Installation): Listed[] {
  const { equipment = [], sensors = [] } = installation.layout;
  const openings = installation.envelope.openings ?? [];
  return [
    ...equipment.map((piece) => ({
      id: piece.actuator_id,
      kind: piece.kind ?? "equipment",
      where: point("base" in piece ? piece.base : piece.position),
      on: "house" as const,
    })),
    ...sensors.map((sensor) => ({
      id: sensor.sensor_id,
      kind: sensor.kind ?? "sensor",
      where: point(sensor.position),
      on: "house" as const,
    })),
    ...openings.map((opening) => ({
      id: opening.opening_id,
      kind: opening.kind,
      where: `${opening.surface_id.replaceAll("_", " ")}, ${metres(opening.centre.x)} along`,
      on: "surface" as const,
    })),
  ];
}
