import { Quaternion, Vector3 } from "three";

import { entityBounds, shapeExtent } from "../debug/overlays";
import type { Point3 } from "../world";
import type { SceneEntity } from "./generated/snapshotTypes";

/**
 * Equipment and sensors moved across the floor (#209). A move is how far an
 * item stands from where its layout places it, along the world's x and y, in
 * metres; the simulator takes moves as part of a layout's name, after this
 * mark, `default~heater:-1:0.5` (`greenhouse_sim.world.moves`), and runs the
 * house with them: another layout, and another run.
 */
export const MOVES_MARK = "~";
// What a move snaps to, in metres.
export const SNAP_M = 0.1;
// Its decimals, which a layout's name writes.
export const SNAP_DECIMALS = 1;
// How far inside the house's walls a moved item keeps, in metres, so that
// a corner on a wall is never a rounding error outside it.
const WALL_CLEARANCE_M = 0.001;
// The kinds that can be moved: the equipment's, by its actuator, and the
// sensors', by their sensor.
const MOVABLE: Readonly<Record<string, string>> = {
  FAN: "actuator_id",
  HEATER: "actuator_id",
  DEHUMIDIFIER: "actuator_id",
  SENSOR: "sensor_id",
  CAMERA: "sensor_id",
};

/** How far a move takes an item, along the world's x and y, in metres. */
export interface Offset {
  dx: number;
  dy: number;
}

export type Moves = Readonly<Record<string, Offset>>;

export const NO_OFFSET: Offset = { dx: 0, dy: 0 };

/** The layout a moved one starts from, or undefined for the scenario's own. */
export function baseLayout(layout: string | undefined): string | undefined {
  if (layout === undefined) {
    return undefined;
  }
  return layout.split(MOVES_MARK)[0];
}

/** A layout's name as an address writes it: its names escaped, the marks
 * between its moves and their distances as they are. */
export function layoutText(layout: string): string {
  return layout
    .split(MOVES_MARK)
    .map((part) =>
      part
        .split(",")
        .map((move) => move.split(":").map(encodeURIComponent).join(":"))
        .join(","),
    )
    .join(MOVES_MARK);
}

/** The moves a layout's name holds, by item; none that are not written as
 * `item:dx:dy`. */
export function movesIn(layout: string | undefined): Moves {
  const written = layout?.split(MOVES_MARK)[1];
  if (written === undefined) {
    return {};
  }
  const moves: Record<string, Offset> = {};
  for (const move of written.split(",")) {
    const [item, dx, dy, ...more] = move.split(":");
    const offset = { dx: Number(dx), dy: Number(dy) };
    if (item && dx && dy && more.length === 0 && Number.isFinite(offset.dx + offset.dy)) {
      moves[item] = offset;
    }
  }
  return moves;
}

/** `layout`'s base with `moves`, by item in order, or the base alone when
 * nothing is moved. */
export function layoutWith(
  layout: string | undefined,
  defaultLayout: string,
  moves: Moves,
): string | undefined {
  const base = baseLayout(layout);
  const items = Object.keys(moves).sort();
  if (items.length === 0) {
    return base === defaultLayout ? undefined : base;
  }
  const written = items.map((item) => {
    const { dx, dy } = moves[item] as Offset;
    return `${item}:${snap(dx)}:${snap(dy)}`;
  });
  return `${base ?? defaultLayout}${MOVES_MARK}${written.join(",")}`;
}

/** `layout` with `item` moved by `by` from where it stands: a move back to
 * where its layout places it is no move. */
export function movedBy(
  layout: string | undefined,
  defaultLayout: string,
  item: string,
  by: Offset,
): string | undefined {
  const moves = { ...movesIn(layout) };
  const was = moves[item] ?? NO_OFFSET;
  const now = { dx: snap(was.dx + by.dx), dy: snap(was.dy + by.dy) };
  if (now.dx === 0 && now.dy === 0) {
    delete moves[item];
  } else {
    moves[item] = now;
  }
  return layoutWith(layout, defaultLayout, moves);
}

/** `layout` with `item` back where its layout places it. */
export function putBack(
  layout: string | undefined,
  defaultLayout: string,
  item: string,
): string | undefined {
  const { [item]: _, ...rest } = movesIn(layout);
  return layoutWith(layout, defaultLayout, rest);
}

/** The item an entity draws, by its actuator or sensor, if it can be moved. */
export function movableItem(entity: SceneEntity): string | null {
  const property = MOVABLE[entity.kind];
  const item = property === undefined ? undefined : entity.properties[property];
  return typeof item === "string" ? item : null;
}

/** A distance to the snap, never `-0`. */
function snap(metres: number): number {
  return Number((Math.round(metres / SNAP_M) * SNAP_M).toFixed(SNAP_DECIMALS)) + 0;
}

/** An offset to the snap. */
export function snapped({ dx, dy }: Offset): Offset {
  return { dx: snap(dx), dy: snap(dy) };
}

/** An entity as it would stand, moved by `by`. */
export function shifted(entity: SceneEntity, by: Offset): SceneEntity {
  const { position } = entity.transform;
  return {
    ...entity,
    transform: {
      ...entity.transform,
      position: { x: position.x + by.dx, y: position.y + by.dy, z: position.z },
    },
  };
}

/**
 * How far `item` can move by `by`, to the snap, keeping inside `house`, the
 * greenhouse's bounds, as the simulator keeps a layout's fixtures: its box
 * stops at the walls. An item that stands outside, a weather station's
 * instrument, is not held in; nor is any without the house's bounds.
 */
export function keptInside(by: Offset, item: SceneEntity, house: SceneEntity | null): Offset {
  if (house === null) {
    return snapped(by);
  }
  const { rotation, position } = house.transform;
  const turn = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
  const back = turn.clone().invert();
  const origin = new Vector3(position.x, position.y, position.z);
  const local = (point: Point3) =>
    new Vector3(point.x, point.y, point.z).sub(origin).applyQuaternion(back);
  const walls = shapeExtent(house.shape);
  const { min, max } = entityBounds(item);
  const corners = [min.x, max.x].flatMap((x) =>
    [min.y, max.y].map((y) => local({ x, y, z: min.z })),
  );
  const lowest = {
    x: Math.min(...corners.map((c) => c.x)),
    y: Math.min(...corners.map((c) => c.y)),
  };
  const highest = {
    x: Math.max(...corners.map((c) => c.x)),
    y: Math.max(...corners.map((c) => c.y)),
  };
  const inside =
    lowest.x >= walls.min.x - WALL_CLEARANCE_M &&
    lowest.y >= walls.min.y - WALL_CLEARANCE_M &&
    highest.x <= walls.max.x + WALL_CLEARANCE_M &&
    highest.y <= walls.max.y + WALL_CLEARANCE_M;
  if (!inside) {
    return snapped(by);
  }
  // The move in the house's own axes, held between its walls, each limit
  // rounded inwards to the snap.
  const along = new Vector3(by.dx, by.dy, 0).applyQuaternion(back);
  const held = (value: number, from: number, to: number) =>
    Math.min(
      Math.max(value, Math.ceil((from + WALL_CLEARANCE_M) / SNAP_M) * SNAP_M),
      Math.floor((to - WALL_CLEARANCE_M) / SNAP_M) * SNAP_M,
    );
  along.set(
    held(along.x, walls.min.x - lowest.x, walls.max.x - highest.x),
    held(along.y, walls.min.y - lowest.y, walls.max.y - highest.y),
    0,
  );
  along.applyQuaternion(turn);
  return snapped({ dx: along.x, dy: along.y });
}
