import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const STYLES = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
// A colour written out, rather than one of the theme's.
const WRITTEN_OUT = /#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(/i;

describe("the stylesheet", () => {
  it("colours every panel's text and background from the panels' theme (#208)", () => {
    // The theme's own colours are named at the top, in its `:root` blocks;
    // a panel written in others stays light, or dark, whatever is chosen.
    const rules = STYLES.replace(/:root[^{]*\{[^}]*\}/g, "");
    const written = [...rules.matchAll(/^\s*(?:color|background(?:-color)?):[^;]*;/gm)]
      .map(([declaration]) => declaration.trim())
      .filter((declaration) => WRITTEN_OUT.test(declaration));

    expect(written).toEqual([]);
  });
});
