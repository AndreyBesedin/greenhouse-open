import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScalarLegend } from "./debug/ScalarLegend";
import { describeShape, Inspector } from "./Inspector";
import type { SceneEntity, SceneSnapshot } from "./scene/generated/snapshotTypes";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);
const PLANT = EXAMPLE.entities.find(
  (entity) => entity.entity_id === "gh_demo_plant_001",
) as SceneEntity;
const ignore = () => undefined;

describe("the inspector", () => {
  it("shows the selected entity's identity, transform, shape and properties", () => {
    const html = renderToStaticMarkup(
      <Inspector
        entity={PLANT}
        overlays={{ box: true, axes: true, label: true }}
        onOverlays={ignore}
        onClear={ignore}
      />,
    );

    expect(html).toContain('data-testid="selected-entity">gh_demo_plant_001<');
    expect(html).toContain('data-testid="selected-position">x 0.50, y 1.60, z 0.00<');
    expect(html).toContain('data-testid="selected-rotation">w 1.000, x 0.000, y 0.000, z 0.000<');
    expect(html).toContain('data-testid="selected-shape">cylinder, radius 0.02 m, height 0.35 m<');
    expect(html).toContain('data-testid="property-visible_height_cm">35.15<');
    expect(html).toContain('data-testid="property-fruits_on_plant">12<');
  });

  it("shows which overlays are drawn", () => {
    const html = renderToStaticMarkup(
      <Inspector
        entity={PLANT}
        overlays={{ box: true, axes: false, label: true }}
        onOverlays={ignore}
        onClear={ignore}
      />,
    );

    expect(html).toContain('<input type="checkbox" checked=""/> Bounding box');
    expect(html).toContain('<input type="checkbox"/> Origin and axes');
    expect(html).toContain('<input type="checkbox" checked=""/> Label');
  });

  it("describes each kind of shape in metres", () => {
    expect(describeShape({ shape: "plane", size_x: 2, size_y: 4.8 })).toBe("plane, 2.00 × 4.80 m");
    expect(describeShape({ shape: "axes", length: 1 })).toBe("axes, 1.00 m");
  });
});

describe("the legend", () => {
  it("names the property and the range its colours span", () => {
    const html = renderToStaticMarkup(
      <ScalarLegend
        colouring={{ property: "visible_height_cm", range: { min: 33.11, max: 36 } }}
      />,
    );

    expect(html).toContain('data-testid="legend-property">visible_height_cm<');
    expect(html).toContain('data-testid="legend-min">33.11<');
    expect(html).toContain('data-testid="legend-max">36<');
    expect(html).toContain("linear-gradient(to right, #440154");
  });
});
