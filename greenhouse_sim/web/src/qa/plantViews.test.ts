import { readFileSync } from "node:fs";

import { PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { CAMERA_FIELD_OF_VIEW_DEG } from "../camera";
import { entityBounds } from "../debug/overlays";
import { checkScene } from "../scene/checkScene";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { worldToViewer } from "../world";
import { QA_PLANTS_POSE, timeLapseDays } from "./plantViews";

const QA_PLANTS: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-plants.json", import.meta.url), "utf8"),
);
// Desktop Chrome's view, which the screenshot test draws in.
const ASPECT = 1280 / 720;

describe("the plants' time lapse", () => {
  it("is a scene the viewer draws, of one plant on days 0, 30, 60 and 90", () => {
    expect(checkScene(QA_PLANTS).ok).toBe(true);
    expect(timeLapseDays(QA_PLANTS)).toEqual([0, 30, 60, 90]);
    const plants = new Set(QA_PLANTS.entities.map((entity) => entity.properties.plant_id));
    expect([...plants].filter((plant) => plant !== undefined)).toEqual(["p01"]);
  });

  it("is seen whole from its view", () => {
    const camera = new PerspectiveCamera(CAMERA_FIELD_OF_VIEW_DEG, ASPECT);
    const position = worldToViewer(QA_PLANTS_POSE.position);
    const target = worldToViewer(QA_PLANTS_POSE.target);
    camera.position.set(position.x, position.y, position.z);
    camera.lookAt(target.x, target.y, target.z);
    camera.updateMatrixWorld();
    for (const entity of QA_PLANTS.entities.filter((e) => e.properties.organ_id !== undefined)) {
      const { min, max } = entityBounds(entity);
      for (const corner of [min, max]) {
        const viewer = worldToViewer(corner);
        const seen = new Vector3(viewer.x, viewer.y, viewer.z).project(camera);
        expect(Math.abs(seen.x), entity.entity_id).toBeLessThan(1);
        expect(Math.abs(seen.y), entity.entity_id).toBeLessThan(1);
      }
    }
  });
});
