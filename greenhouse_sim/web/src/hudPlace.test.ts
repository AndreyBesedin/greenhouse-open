import { describe, expect, it } from "vitest";

import { type Box, isMoved, UNMOVED, unmoved, within } from "./hudPlace";

// A window 1,280 by 720 pixels, and a panel 300 by 400 in its top right
// corner, 12 pixels in from each edge.
const WINDOW: Box = { left: 0, top: 0, right: 1280, bottom: 720 };
const PLACE: Box = { left: 968, top: 12, right: 1268, bottom: 412 };

describe("a panel moved within the window", () => {
  it("goes where it is wanted when it stays within", () => {
    expect(within({ x: -500, y: 200 }, PLACE, WINDOW)).toEqual({ x: -500, y: 200 });
  });

  it("stops at each edge it would cross, and goes as far as it can along it", () => {
    expect(within({ x: 100, y: -50 }, PLACE, WINDOW)).toEqual({ x: 12, y: -12 });
    expect(within({ x: -5000, y: 5000 }, PLACE, WINDOW)).toEqual({ x: -968, y: 308 });
  });

  it("keeps its top within the window when it is taller than the window", () => {
    const tall: Box = { ...PLACE, bottom: 1012 };

    expect(within({ x: -100, y: 200 }, tall, WINDOW)).toEqual({ x: -100, y: -12 });
  });

  it("comes back within when the window shrinks under it", () => {
    const narrower: Box = { ...WINDOW, right: 900 };

    expect(within(UNMOVED, PLACE, narrower)).toEqual({ x: -368, y: 0 });
  });

  it("is told apart from one in its own place", () => {
    expect(isMoved(UNMOVED)).toBe(false);
    expect(isMoved({ x: 0, y: -1 })).toBe(true);
  });

  it("is found unmoved by taking its offset back", () => {
    const drawn: Box = { left: 468, top: 212, right: 768, bottom: 612 };

    expect(unmoved(drawn, { x: -500, y: 200 })).toEqual(PLACE);
  });
});
