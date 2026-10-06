import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { greenhouseExtent } from "./greenhouseViews";
import {
  eaveHeight,
  isLayoutPlan,
  QA_LAYOUT_VIEWS,
  qaLayoutPose,
  qaLayoutSection,
  qaLayoutView,
} from "./layoutViews";

const QA_LAYOUT: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-layout.json", import.meta.url), "utf8"),
);
// The QA greenhouse: 16 by 9.6 m, its eaves at 4 m.
const EXTENT = { length: 16, width: 9.6, height: 4.65 };

describe("the layout's QA views", () => {
  it("are chosen in the address, the top view by default", () => {
    expect(qaLayoutView("")).toBe("top");
    expect(qaLayoutView("?view=top")).toBe("top");
    expect(qaLayoutView("?view=between-rows")).toBe("between-rows");
    expect(qaLayoutView("?view=occluded")).toBe("occluded");
    expect(qaLayoutView("?view=sideways")).toBeNull();
  });

  it("find the QA greenhouse's size and its eaves in the scene", () => {
    expect(greenhouseExtent(QA_LAYOUT)).toEqual(EXTENT);
    expect(eaveHeight(QA_LAYOUT)).toBeCloseTo(4);
  });

  it("look down on the middle of the house, cut just below its eaves", () => {
    const pose = qaLayoutPose("top", EXTENT);

    expect(pose.target).toEqual({ x: 8, y: 4.8, z: 0 });
    expect(pose.position.x).toBe(8);
    expect(pose.position.z).toBeGreaterThan(EXTENT.height);
    expect(qaLayoutSection("top", 4)).toEqual({ normal: { x: 0, y: 0, z: -1 }, distance: 3.95 });
  });

  it("ride a rail down the path between the second and third rows", () => {
    const pose = qaLayoutPose("between-rows", EXTENT);

    // Between the rail's tubes, 0.55 m apart around y = 4.4 m, under the
    // wires at 3.5 m, past the front aisle, looking straight down the path.
    expect(pose.position).toEqual({ x: 1.6, y: 4.4, z: 1 });
    expect(pose.target).toEqual({ x: 14, y: 4.4, z: 1 });
  });

  it("look across a row from low in the path before it", () => {
    const pose = qaLayoutPose("occluded", EXTENT);

    // Below the gutters' 0.6 m tops, in the first path, looking past the
    // second row (y = 3.6 m).
    expect(pose.position.z).toBeLessThan(0.6);
    expect(pose.position.y).toBe(2.8);
    expect(pose.target.y).toBeGreaterThan(3.6);
  });

  it("cut and colour only the plan", () => {
    expect(QA_LAYOUT_VIEWS.filter(isLayoutPlan)).toEqual(["top"]);
    expect(qaLayoutSection("between-rows", 4)).toBeNull();
    expect(qaLayoutSection("occluded", 4)).toBeNull();
  });
});
