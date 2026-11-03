import { describe, expect, it } from "vitest";

import { BUNDLE_BUDGET_KB, overBudget, weigh } from "./bundleBudget";

describe("the viewer's bundle budget (AUDIT.20)", () => {
  it("weighs a build's scripts and styles, and nothing else", () => {
    expect(
      weigh([
        { fileName: "assets/index-1.js", bytes: 1_585_759 },
        { fileName: "assets/index-2.css", bytes: 15_577 },
        { fileName: "assets/worker.js", bytes: 241 },
        { fileName: "favicon.svg", bytes: 900 },
      ]),
    ).toEqual({ js: 1586, css: 15.577 });
  });

  it("passes a build within it, and says what weighs over it", () => {
    expect(overBudget({ js: 1586, css: 16 }, BUNDLE_BUDGET_KB)).toEqual([]);
    // Over by a little more than a kilobyte each, whatever the budget is.
    const { js, css } = BUNDLE_BUDGET_KB;
    expect(overBudget({ js: js + 1.4, css: css + 1.4 }, BUNDLE_BUDGET_KB)).toEqual([
      `the viewer's js weighs ${Math.round(js + 1.4)} kB minified, over its budget of ${js} kB (src/bundleBudget.ts)`,
      `the viewer's css weighs ${Math.round(css + 1.4)} kB minified, over its budget of ${css} kB (src/bundleBudget.ts)`,
    ]);
  });
});
