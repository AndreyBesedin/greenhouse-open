import { describe, expect, it } from "vitest";

import { rowNumbers, withCrop } from "./edits";
import type { Installation } from "./generated/assessedTypes";

const HOUSE = {
  installation_id: "house",
  name: "House",
  envelope: {},
  layout: { crop_rows: { rows: 3 } },
  row_crops: [
    { row: 1, crop_model: "simple", variety: "cherry_tomato" },
    { row: 3, crop_model: "simple", variety: "cherry_tomato" },
  ],
} as unknown as Installation;

describe("a crop given to many rows at once (P12.2)", () => {
  it("changes the rows chosen and no other, in their order", () => {
    const given = withCrop(HOUSE, [2, 3], { crop_model: "organ", variety: "beefsteak" });

    expect(rowNumbers(given)).toEqual([1, 2, 3]);
    expect(given.row_crops).toEqual([
      { row: 1, crop_model: "simple", variety: "cherry_tomato" },
      { row: 2, crop_model: "organ", variety: "beefsteak" },
      { row: 3, crop_model: "organ", variety: "beefsteak" },
    ]);
    // The installation before stays as it was, for an undo.
    expect(HOUSE.row_crops).toHaveLength(2);
  });

  it("changes nothing when no row, a row of none, or no variety is given", () => {
    const crop = { crop_model: "simple" as const, variety: "cherry_tomato" };
    expect(() => withCrop(HOUSE, [], crop)).toThrow("choose at least one row");
    expect(() => withCrop(HOUSE, [4], crop)).toThrow("choose rows from 1 to 3");
    expect(() => withCrop(HOUSE, [1], { ...crop, variety: " " })).toThrow("name the variety");
  });
});
