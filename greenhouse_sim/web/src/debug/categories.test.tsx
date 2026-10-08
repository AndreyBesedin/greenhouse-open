import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { CategoryLegend } from "./CategoryLegend";
import {
  CATEGORY_COLORS,
  categoriesIn,
  categoryColor,
  ENVELOPE_CATEGORIES,
  EQUIPMENT_CATEGORIES,
  isEnvelopeCategory,
  LAYOUT_CATEGORIES,
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
      "FAN",
      "HEATER",
      "DEHUMIDIFIER",
    ]);
    const others = EXAMPLE.entities.filter((entity) => categoryColor(entity.kind) === null);
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
    const categories = [...ENVELOPE_CATEGORIES, ...LAYOUT_CATEGORIES, ...EQUIPMENT_CATEGORIES];
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
    const others = QA_LAYOUT.entities.filter((entity) => categoryColor(entity.kind) === null);
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
    const html = renderToStaticMarkup(<CategoryLegend categories={["WALKWAY", "FAN", "HEATER"]} />);

    expect(html).toContain('aria-label="Layout categories"');
    expect(html).toContain('aria-label="Equipment categories"');
    expect(html.match(/data-testid="equipment-category"/g)).toHaveLength(2);
    expect(html).toContain(`background:${CATEGORY_COLORS.HEATER}`);
    expect(html).toContain(">fan</li>");
  });

  it("leave a scene with no envelope its layout's legend alone", () => {
    const html = renderToStaticMarkup(<CategoryLegend categories={["WALKWAY"]} />);

    expect(html).not.toContain("Surface categories");
  });
});
