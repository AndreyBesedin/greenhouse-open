import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScalarLegend } from "./debug/ScalarLegend";
import { describeDimensions, describeShape, Inspector } from "./Inspector";
import type { SceneEntity, SceneSnapshot } from "./scene/generated/snapshotTypes";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);
const PLANT = EXAMPLE.entities.find(
  (entity) => entity.entity_id === "climate_box_plant_001",
) as SceneEntity;
const ignore = () => undefined;
// The canonical layout (`tests/test_scene_schema.py`).
const QA_LAYOUT: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/qa-layout.json", import.meta.url), "utf8"),
);

function layoutEntity(entityId: string): SceneEntity {
  const entity = QA_LAYOUT.entities.find((each) => each.entity_id === `qa_layout_${entityId}`);
  if (entity === undefined) {
    throw new Error(`the QA layout has no ${entityId}`);
  }
  return entity;
}

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

    expect(html).toContain('data-testid="selected-entity">climate_box_plant_001<');
    // On its gutter's slab, at the first row's first place.
    expect(html).toContain('data-testid="selected-position">x 2.25, y 2.40, z 0.67<');
    expect(html).toContain('data-testid="selected-rotation">w 1.000, x 0.000, y 0.000, z 0.000<');
    expect(html).toContain('data-testid="selected-shape">cylinder, radius 0.02 m, height 0.35 m<');
    expect(html).toContain('data-testid="property-visible_height_cm">34.99<');
    expect(html).toContain('data-testid="property-fruits_on_plant">4<');
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
    expect(describeShape({ shape: "box", size_x: 4, size_y: 6.4, size_z: 4 })).toBe(
      "box, 4.00 × 6.40 × 4.00 m",
    );
    const gable = [
      { x: 0, y: 0 },
      { x: 6.4, y: 0 },
      { x: 6.4, y: 3 },
      { x: 3.2, y: 4.3 },
      { x: 0, y: 3 },
    ];
    expect(describeShape({ shape: "polygon", points: gable as never })).toBe("polygon, 5 corners");
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

describe("what the inspector says an entity is", () => {
  it("names its type in words, and its size by what each measure is", () => {
    const html = renderToStaticMarkup(
      <Inspector
        entity={layoutEntity("row_1_support_1")}
        overlays={{ box: true, axes: true, label: true }}
        onOverlays={ignore}
        onClear={ignore}
      />,
    );

    expect(html).toContain('data-testid="selected-type">crop gutter<');
    expect(html).toContain(
      'data-testid="selected-dimensions">length 5.90 m, width 0.30 m, height 0.12 m<',
    );
  });

  it("measures a standing cylinder's height, and a lying one's length", () => {
    expect(describeDimensions(PLANT)).toBe("diameter 0.04 m, height 0.35 m");
    expect(describeDimensions(layoutEntity("heating_pipes_left_1"))).toBe(
      "diameter 0.05 m, length 14.50 m",
    );
  });
});
