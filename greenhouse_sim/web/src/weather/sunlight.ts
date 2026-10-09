import { inWorld } from "../debug/dimensions";
import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";
import { SUN_COLOR, type WeatherAtAMoment, type WeatherDay } from "./weather";

// The sun's light stands this many times the house's longer side from its
// middle, and its shadows cover the house and this much around it.
const LIGHT_REACH = 2;
const SHADOW_MARGIN_M = 4;
// The sun's path across the sky is drawn at the sun marker's reach.
const PATH_REACH = 1.5;

/** Where the scene's sunlight comes from: the light's position and the point
 * it shines at, in the world's axes, and how far around that its shadows
 * reach. */
export interface SunLightPose {
  position: Point3;
  target: Point3;
  shadowHalfWidthM: number;
  distanceM: number;
}

function houseOf(
  snapshot: SceneSnapshot,
): { middle: Point3; longer: number; across: number } | null {
  const bounds = snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS");
  if (bounds?.shape.shape !== "box") {
    return null;
  }
  const { size_x, size_y, size_z } = bounds.shape;
  return {
    middle: inWorld(bounds.transform, { x: 0, y: 0, z: size_z / 2 }),
    longer: Math.max(size_x, size_y),
    across: Math.hypot(size_x, size_y, size_z),
  };
}

/**
 * The scene's sunlight for a sun in `direction` (a unit vector towards it, in
 * the world's axes): from beyond the house in that direction, at the house's
 * middle, its shadows covering the whole house; null for a scene without the
 * house's bounds.
 */
export function sunLightPose(snapshot: SceneSnapshot, direction: Point3): SunLightPose | null {
  const house = houseOf(snapshot);
  if (house === null) {
    return null;
  }
  const distanceM = house.longer * LIGHT_REACH;
  const { middle } = house;
  return {
    position: {
      x: middle.x + direction.x * distanceM,
      y: middle.y + direction.y * distanceM,
      z: middle.z + direction.z * distanceM,
    },
    target: middle,
    shadowHalfWidthM: house.across / 2 + SHADOW_MARGIN_M,
    distanceM,
  };
}

/** How the scene is lit at a moment outside: by the sun, while it is up;
 * by the sky's ambient light alone, while it is down ("night"); or by the
 * viewer's fixed light (null), for a scene without the house's bounds. */
export function sceneSunlight(
  snapshot: SceneSnapshot,
  weather: WeatherAtAMoment,
): SunLightPose | "night" | null {
  if (weather.sun.elevation_deg <= 0) {
    return houseOf(snapshot) === null ? null : "night";
  }
  return sunLightPose(snapshot, weather.sunDirection);
}

/** The sun's path across the sky through the day, as lines between its
 * positions while it is up, at the sun marker's reach from the house. */
export function sunPathOverlays(snapshot: SceneSnapshot, day: WeatherDay): OverlayPrimitive[] {
  const house = houseOf(snapshot);
  if (house === null) {
    return [];
  }
  const reach = house.longer * PATH_REACH;
  const { middle } = house;
  const at = (towards: Point3) => ({
    x: middle.x + towards.x * reach,
    y: middle.y + towards.y * reach,
    z: middle.z + towards.z * reach,
  });
  const lines: OverlayPrimitive[] = [];
  day.sunDirections.forEach((towards, index) => {
    const next = day.sunDirections[index + 1];
    const up = day.sun[index]?.elevation_deg ?? 0;
    const nextUp = day.sun[index + 1]?.elevation_deg ?? 0;
    if (next !== undefined && up > 0 && nextUp > 0) {
      lines.push({
        id: `sun-path-${index}`,
        kind: "line",
        from: at(towards),
        to: at(next),
        color: SUN_COLOR,
      });
    }
  });
  return lines;
}
