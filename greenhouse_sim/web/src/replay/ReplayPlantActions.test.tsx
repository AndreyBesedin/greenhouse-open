// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

import type { SceneEntity } from "../scene/generated/snapshotTypes";
import { button, click, render } from "../testing/render";
import { ReplayPlantActions } from "./ReplayPlantActions";

const LEAF: SceneEntity = {
  entity_id: "p01_n02_leaf_0",
  kind: "LEAF",
  transform: { position: { x: 0, y: 0, z: 0 }, rotation: { w: 1, x: 0, y: 0, z: 0 } },
  shape: { shape: "sphere", radius: 0.01 },
  color: { r: 0, g: 0, b: 0 },
  material: null,
  label: null,
  properties: { organ_id: "p01_n02_leaf", organ_kind: "leaf", plant_id: "p01" },
};

describe("a plant's work in a replay", () => {
  it("is asked of the epoch at once while it is being computed", () => {
    const onWork = vi.fn();
    const onFork = vi.fn();
    const shown = render(
      <ReplayPlantActions entity={LEAF} computing={true} onWork={onWork} onFork={onFork} />,
    );

    click(button(shown.container, "Remove this leaf"));

    expect(onWork).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "remove_leaf", plantId: "p01", target: "p01_n02_leaf" }),
    );
    expect(onFork).not.toHaveBeenCalled();
    expect(shown.container.querySelector('[data-testid="fork-question"]')).toBeNull();
  });

  it("is a fork once the epoch has ended, made only once it is asked for", () => {
    const onWork = vi.fn();
    const onFork = vi.fn();
    const shown = render(
      <ReplayPlantActions entity={LEAF} computing={false} onWork={onWork} onFork={onFork} />,
    );

    click(button(shown.container, "Lower the stem"));
    expect(onFork).not.toHaveBeenCalled();
    expect(button(shown.container, "Make the fork").classList).toContain("ds-button-primary");
    click(button(shown.container, "Make the fork"));

    expect(onFork).toHaveBeenCalledWith(expect.objectContaining({ kind: "lower_stem" }));
    expect(onWork).not.toHaveBeenCalled();
  });

  it("offers nothing without an organ selected", () => {
    const shown = render(
      <ReplayPlantActions entity={null} computing={true} onWork={vi.fn()} onFork={vi.fn()} />,
    );

    expect(shown.container.querySelector("button")).toBeNull();
  });
});
