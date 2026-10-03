import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hud } from "./Hud";

const ignore = () => undefined;

describe("the HUD", () => {
  it("offers a button per camera preset", () => {
    const html = renderToStaticMarkup(<Hud sample={null} pointer={null} onPreset={ignore} />);

    for (const label of ["Top", "Front", "Side", "Isometric"]) {
      expect(html).toContain(`>${label}</button>`);
    }
  });

  it("shows readouts once the view has been sampled", () => {
    const html = renderToStaticMarkup(
      <Hud
        sample={{ framesPerSecond: 59.6, camera: { x: 5.196, y: -5.196, z: 5.196 }, objects: 8 }}
        pointer={{ x: 1.234, y: -0.5, z: 0 }}
        onPreset={ignore}
      />,
    );

    expect(html).toContain("x 5.20, y -5.20, z 5.20");
    expect(html).toContain("x 1.23, y -0.50");
    expect(html).toContain("60 fps");
    expect(html).toContain('data-testid="object-count">8<');
  });

  it("says nothing is measured yet before the first sample", () => {
    const html = renderToStaticMarkup(<Hud sample={null} pointer={null} onPreset={ignore} />);

    expect(html).toContain('data-testid="camera-position">…<');
    expect(html).toContain('data-testid="pointer-position">—<');
  });
});
