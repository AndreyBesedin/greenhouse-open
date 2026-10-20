import { describe, expect, it } from "vitest";

import { CHART_WIDTH, chartY, polylinePoints } from "./chart";

describe("a small chart", () => {
  it("places a value up its range, the least at its foot, the most at its head", () => {
    expect(chartY(10, { min: 10, max: 20 }, 28)).toBe(28);
    expect(chartY(20, { min: 10, max: 20 }, 28)).toBe(0);
    expect(chartY(15, { min: 10, max: 20 }, 28)).toBe(14);
    // A range of one value draws it across the middle, not at no height.
    expect(chartY(7, { min: 7, max: 7 }, 28)).toBe(14);
  });

  it("writes its points to a decimal, a missing value at the range's least", () => {
    const points = polylinePoints(
      [0, CHART_WIDTH / 3, CHART_WIDTH],
      [10, 20],
      { min: 10, max: 20 },
      28,
    );

    expect(points).toBe("0.0,28.0 80.0,0.0 240.0,28.0");
  });
});
