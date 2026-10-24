import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { present } from "../testing/present";
import { CategoryLegend } from "./CategoryLegend";
import {
  CATEGORY_COLORS,
  categoriesIn,
  categoryColor,
  categoryOf,
  ENVELOPE_CATEGORIES,
  EQUIPMENT_CATEGORIES,
  isEnvelopeCategory,
  LAYOUT_CATEGORIES,
  SENSOR_CATEGORIES,
  semanticType,
} from "./categories";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
// The canonical layout (`tests/test_scene_schema.py`).
const QA_LAYOUT: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-layout.json", import.meta.url), "utf8"),
);

describe("the envelope's categories", () => {
  it("each have a colour of their own", () => {
    const colours = ENVELOPE_CATEGORIES.map((category) => CATEGORY_COLORS[category]);

    expect(new Set(colours).size).toBe(ENVELOPE_CATEGORIES.length);
  });

  it("cover every part of the example greenhouse, and nothing else of it", () => {
    expect(categoriesIn(EXAMPLE)).toEqual([
      "FLOOR",
      "WALL",
      "ROOF",
      "VENT",
      "DOOR",
      "GUTTER",
      "FRAME",
      "PLANTING_POSITION",
      "CROP_GUTTER",
      "SLAB",
      "WALKWAY",
      "WIRE",
      "MOVES_AIR",
      "HEATS",
      "DRIES",
      "SENSOR",
      "CAMERA",
    ]);
    const others = EXAMPLE.entities.filter((entity) => categoryColor(entity) === null);
    expect(new Set(others.map((entity) => entity.kind))).toEqual(
      new Set(["AXES", "GREENHOUSE_BOUNDS", "PLANT"]),
    );
  });

  it("are listed in the legend with their colours", () => {
    const html = renderToStaticMarkup(<CategoryLegend categories={["FLOOR", "VENT"]} />);

    expect(html).toContain('aria-label="Surface categories"');
    expect(html).toContain(`background:${CATEGORY_COLORS.FLOOR}`);
    expect(html).toContain(">floor</li>");
    expect(html).toContain(">vent</li>");
  });
});

describe("the layout's categories", () => {
  it("each have a colour of their own, apart from the envelope's and the equipment's", () => {
    const categories = [
      ...ENVELOPE_CATEGORIES,
      ...LAYOUT_CATEGORIES,
      ...EQUIPMENT_CATEGORIES,
      ...SENSOR_CATEGORIES,
    ];
    const colours = categories.map((category) => CATEGORY_COLORS[category]);

    expect(new Set(colours).size).toBe(categories.length);
  });

  it("cover every part of the canonical layout", () => {
    expect(categoriesIn(QA_LAYOUT).filter((category) => !isEnvelopeCategory(category))).toEqual([
      "PLANTING_POSITION",
      "CROP_GUTTER",
      "SLAB",
      "WALKWAY",
      "SERVICE_ZONE",
      "KEEP_OUT",
      "RAIL",
      "PIPE",
      "WIRE",
      "OBSTACLE",
    ]);
    const others = QA_LAYOUT.entities.filter((entity) => categoryColor(entity) === null);
    expect(new Set(others.map((entity) => entity.kind))).toEqual(
      new Set(["AXES", "GREENHOUSE_BOUNDS"]),
    );
  });

  it("are listed in a legend of their own, apart from the surfaces'", () => {
    const html = renderToStaticMarkup(
      <CategoryLegend categories={["FLOOR", "WALKWAY", "KEEP_OUT"]} />,
    );

    expect(html).toContain('aria-label="Surface categories"');
    expect(html).toContain('aria-label="Layout categories"');
    expect(html).toContain('data-testid="layout-category"');
    expect(html).toContain(`background:${CATEGORY_COLORS.KEEP_OUT}`);
    expect(html).toContain(">keep-out</li>");
  });

  it("list the equipment in a legend of its own", () => {
    const html = renderToStaticMarkup(
      <CategoryLegend categories={["WALKWAY", "MOVES_AIR", "HEATS"]} />,
    );

    expect(html).toContain('aria-label="Layout categories"');
    expect(html).toContain('aria-label="Equipment categories"');
    expect(html.match(/data-testid="equipment-category"/g)).toHaveLength(2);
    expect(html).toContain(`background:${CATEGORY_COLORS.HEATS}`);
    expect(html).toContain(">moving air</li>");
  });

  it("list the sensors in a legend of their own", () => {
    const html = renderToStaticMarkup(
      <CategoryLegend categories={["MOVES_AIR", "SENSOR", "CAMERA"]} />,
    );

    expect(html).toContain('aria-label="Equipment categories"');
    expect(html).toContain('aria-label="Sensor categories"');
    expect(html.match(/data-testid="sensor-category"/g)).toHaveLength(2);
    expect(html).toContain(`background:${CATEGORY_COLORS.CAMERA}`);
  });

  it("leave a scene with no envelope its layout's legend alone", () => {
    const html = renderToStaticMarkup(<CategoryLegend categories={["WALKWAY"]} />);

    expect(html).not.toContain("Surface categories");
  });
});

describe("the equipment's categories", () => {
  it("are what each piece is for, whatever its kind, and its kind is what it is", () => {
    const fan = present(
      EXAMPLE.entities.find((entity) => entity.kind === "EQUIPMENT"),
      "the example's fan",
    );
    const fogger: SceneEntity = {
      ...fan,
      properties: { ...fan.properties, device_kind: "fogger", does: "dries" },
    };
    const doser: SceneEntity = {
      ...fan,
      properties: { device_kind: "co2_doser", does: "adds_co2" },
    };

    expect([categoryOf(fan), semanticType(fan)]).toEqual(["MOVES_AIR", "fan"]);
    expect([categoryOf(fogger), semanticType(fogger)]).toEqual(["DRIES", "fogger"]);
    expect(categoryColor(fogger)).toEqual(categoryColor({ ...fan, properties: { does: "dries" } }));
    // What the viewer has no category for is still named by its kind.
    expect([categoryOf(doser), categoryColor(doser), semanticType(doser)]).toEqual([
      null,
      null,
      "co2 doser",
    ]);
  });
});
