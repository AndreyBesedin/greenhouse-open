import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { plantNameOverlays } from "./names";

function part(entityId: string, plantId: string | null, x: number, z: number): SceneEntity {
  return {
    entity_id: entityId,
    kind: "INTERNODE",
    transform: { position: { x, y: 0, z }, rotation: { w: 1, x: 0, y: 0, z: 0 } },
    shape: { shape: "sphere", radius: 0.01 },
    color: { r: 0, g: 0, b: 0 },
    properties: plantId === null ? {} : { plant_id: plantId },
  } as SceneEntity;
}

const ROW = {
  schema_version: 13,
  greenhouse_id: "plant_lab",
  simulated_day: 0,
  entities: [
    part("ground", null, 0, 0),
    part("p01_n01_internode", "p01", 0, 0),
    part("p01_n05_leaf_terminal", "p01", 0.1, 0.4),
    part("p02_n01_internode", "p02", 0.5, 0),
    part("p02_n03_leaf_terminal", "p02", 0.6, 0.2),
  ],
} as unknown as SceneSnapshot;

describe("the plants' names", () => {
  it("float over each plant's base, above its highest organ", () => {
    const labels = plantNameOverlays(ROW).filter((overlay) => overlay.kind === "label");

    expect(labels.map((label) => label.kind === "label" && label.text)).toEqual(["p01", "p02"]);
    expect(labels[0]?.kind === "label" && labels[0].position).toEqual({
      x: 0,
      y: 0,
      z: expect.closeTo(0.6),
    });
    expect(labels[1]?.kind === "label" && labels[1].position.x).toBe(0.5);
  });
});
