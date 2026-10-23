// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { renderHook } from "../testing/renderHook";
import { ALL_OVERLAYS } from "./overlays";
import { useSceneOverlays } from "./useSceneOverlays";

function part(entityId: string, plantId: string, x: number, z: number): SceneEntity {
  return {
    entity_id: entityId,
    kind: "INTERNODE",
    transform: { position: { x, y: 0, z }, rotation: { w: 1, x: 0, y: 0, z: 0 } },
    shape: { shape: "sphere", radius: 0.01 },
    color: { r: 0, g: 0, b: 0 },
    material: null,
    label: null,
    properties: { plant_id: plantId },
  };
}

const ROW: SceneSnapshot = {
  schema_version: 13,
  greenhouse_id: "plant_lab",
  simulated_day: 0,
  entities: [part("p01_n01_internode", "p01", 0, 0), part("p02_n01_internode", "p02", 0.5, 0)],
};

type Props = Parameters<typeof useSceneOverlays>[0];

const NOTHING_ASKED: Props = {
  snapshot: ROW,
  sunlit: false,
  outside: null,
  sunsDay: null,
  flowing: null,
  probes: [],
  probedField: null,
  probeQuantity: null,
  drawnSelected: null,
  toggles: ALL_OVERLAYS,
  showDimensions: false,
  showingNames: false,
  lightOn: null,
};

function labels(props: Props): (string | false)[] {
  const hook = renderHook(useSceneOverlays, props);
  return hook.current.overlays
    .filter((overlay) => overlay.kind === "label")
    .map((overlay) => overlay.kind === "label" && overlay.text);
}

describe("useSceneOverlays", () => {
  it("draws nothing over a scene that asks for nothing", () => {
    const hook = renderHook(useSceneOverlays, NOTHING_ASKED);

    expect(hook.current.overlays).toEqual([]);
    expect(hook.current.sunlight).toBeNull();
    expect(hook.current.sunNow).toEqual([]);
    expect([...(hook.current.kindsShown ?? [])]).toEqual(["INTERNODE"]);
  });

  it("names the plants only when asked to", () => {
    expect(labels({ ...NOTHING_ASKED, showingNames: true })).toEqual(["p01", "p02"]);
    expect(labels(NOTHING_ASKED)).toEqual([]);
  });

  it("outlines the item selected, where it is drawn", () => {
    const hook = renderHook(useSceneOverlays, {
      ...NOTHING_ASKED,
      drawnSelected: ROW.entities[1] ?? null,
    });

    expect(hook.current.overlays.length).toBeGreaterThan(0);
  });

  it("draws nothing without a scene", () => {
    const hook = renderHook(useSceneOverlays, {
      ...NOTHING_ASKED,
      snapshot: null,
      showingNames: true,
      showDimensions: true,
    });

    expect(hook.current.overlays).toEqual([]);
    expect(hook.current.kindsShown).toBeNull();
  });
});
