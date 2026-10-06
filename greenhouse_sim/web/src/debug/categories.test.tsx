import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { CategoryLegend } from "./CategoryLegend";
import { CATEGORY_COLORS, categoriesIn, categoryColor, ENVELOPE_CATEGORIES } from "./categories";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
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
