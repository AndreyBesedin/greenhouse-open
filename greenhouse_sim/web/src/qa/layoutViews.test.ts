import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { greenhouseExtent } from "./greenhouseViews";
import { eaveHeight, qaLayoutPose, qaLayoutSection, qaLayoutView } from "./layoutViews";

const QA_LAYOUT: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-layout.json", import.meta.url), "utf8"),
);
// The QA greenhouse: 16 by 9.6 m, its eaves at 4 m.
const EXTENT = { length: 16, width: 9.6, height: 4.65 };

describe("the layout's QA views", () => {
  it("are chosen in the address, the top view by default", () => {
    expect(qaLayoutView("")).toBe("top");
    expect(qaLayoutView("?view=top")).toBe("top");
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
});
