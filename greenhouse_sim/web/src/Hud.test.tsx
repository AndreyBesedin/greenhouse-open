// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { Hud } from "./Hud";
import { button, click, type Rendered, render, said } from "./testing/render";

const ignore = () => undefined;
const SAMPLE = {
  framesPerSecond: 59.6,
  frameTimeMs: 16.78,
  worstFrameMs: 33.4,
  drawCalls: 12,
  triangles: 123456,
  geometries: 9,
  textures: 0,
  heapBytes: 47 * 1024 * 1024,
  camera: { x: 5.196, y: -5.196, z: 5.196 },
  objects: 8,
};

describe("the HUD", () => {
  let hud: Rendered | undefined;
  afterEach(() => hud?.unmount());

  it("moves the camera to the preset whose button is pressed", () => {
    const onPreset = vi.fn();
    hud = render(<Hud sample={null} pointer={null} onPreset={onPreset} onCommand={ignore} />);

    for (const label of ["Top", "Front", "Side", "Isometric"]) {
      click(button(hud.container, label));
    }

    expect(onPreset.mock.calls).toEqual([["top"], ["front"], ["side"], ["isometric"]]);
  });

  it("shows readouts once the view has been sampled", () => {
    hud = render(
      <Hud
        sample={SAMPLE}
        pointer={{ x: 1.234, y: -0.5, z: 0 }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );
    const { container } = hud;

    expect(said(container, "camera-position")).toBe("x 5.20, y -5.20, z 5.20");
    expect(said(container, "pointer-position")).toBe("x 1.23, y -0.50");
    expect(said(container, "frame-rate")).toBe("60 fps");
    expect(said(container, "object-count")).toBe("8");
    expect(said(container, "frame-time")).toBe("16.8 ms, worst 33.4 ms");
    expect(said(container, "draw-calls")).toBe("12 (123,456 triangles)");
    expect(said(container, "memory")).toBe("9 geometries, 0 textures, 47 MiB heap");
  });

  it("says nothing is measured yet before the first sample", () => {
    hud = render(<Hud sample={null} pointer={null} onPreset={ignore} onCommand={ignore} />);

    expect(said(hud.container, "camera-position")).toBe("…");
    expect(said(hud.container, "pointer-position")).toBe("—");
  });
});
