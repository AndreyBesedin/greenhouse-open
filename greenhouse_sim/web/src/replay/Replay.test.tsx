// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type Rendered, render } from "../testing/render";
import { Replay } from "./Replay";

// The page itself, so that a suite with no browser reads this file: two merged
// changes each declared `refused` here, and every test still passed.
describe("Replay", () => {
  let shown: Rendered | null = null;

  afterEach(() => {
    shown?.unmount();
    shown = null;
  });

  it("says so when its address names no run", () => {
    shown = render(<Replay search="" />);
    expect(shown.container.textContent).toContain("names no run to replay");
  });
});
