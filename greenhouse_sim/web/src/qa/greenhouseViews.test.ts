import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { checkScene } from "../scene/checkScene";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  greenhouseExtent,
  type QA_GREENHOUSE_VIEWS,
  qaGreenhousePose,
  qaGreenhouseSection,
  qaGreenhouseView,
} from "./greenhouseViews";

const QA_GREENHOUSE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-greenhouse.json", import.meta.url), "utf8"),
);
const EXTENT = { length: 16, width: 9.6, height: 4.65 };

function inside(point: { x: number; y: number; z: number }): boolean {
  return (
    point.x > 0 &&
    point.x < EXTENT.length &&
    point.y > 0 &&
    point.y < EXTENT.width &&
    point.z > 0 &&
    point.z < EXTENT.height
  );
}

describe("the QA greenhouse", () => {
  it("is a scene the viewer draws, 16 by 9.6 m and 4.65 m high", () => {
    expect(checkScene(QA_GREENHOUSE).ok).toBe(true);
    expect(greenhouseExtent(QA_GREENHOUSE)).toEqual({
      length: 16,
      width: expect.closeTo(9.6),
      height: 4.65,
    });
  });

  it("is seen from outside, from inside along an aisle, from above and in section", () => {
    const pose = (view: (typeof QA_GREENHOUSE_VIEWS)[number]) => qaGreenhousePose(view, EXTENT);

    expect(inside(pose("outside").position)).toBe(false);
    expect(inside(pose("aisle").position)).toBe(true);
    expect(pose("aisle").target.x).toBeLessThan(pose("aisle").position.x);
    expect(pose("top").position.z).toBeGreaterThan(EXTENT.height);
    expect(pose("section").position.x).toBeGreaterThan(EXTENT.length / 2);
  });

  it("is cut at the middle of its length in section, and only there", () => {
    expect(qaGreenhouseSection("section", EXTENT)).toEqual({
      normal: { x: -1, y: 0, z: 0 },
      distance: EXTENT.length / 2,
    });
    for (const view of ["outside", "aisle", "top"] as const) {
      expect(qaGreenhouseSection(view, EXTENT)).toBeNull();
    }
  });

  it.each([
    ["", "outside"],
    ["?view=aisle", "aisle"],
    ["?view=section", "section"],
    ["?view=sideways", null],
  ])("reads %j as the %s view", (search, view) => {
    expect(qaGreenhouseView(search)).toBe(view);
  });
});
