import { describe, expect, it } from "vitest";

import { formatMetres, formatPoint, framesPerSecond } from "./readouts";

describe("HUD readouts", () => {
  it("measures frames per second over a sampling window", () => {
    expect(framesPerSecond(30, 500)).toBe(60);
    expect(framesPerSecond(15, 250)).toBe(60);
  });

  it("reports no frame rate for an empty window", () => {
    expect(framesPerSecond(0, 0)).toBe(0);
  });

  it("writes positions to the centimetre", () => {
    expect(formatPoint({ x: 5.196, y: -5.196, z: 5.2 })).toBe("x 5.20, y -5.20, z 5.20");
  });

  it("never writes a negative zero", () => {
    expect(formatMetres(-0.001)).toBe("0.00");
    expect(formatMetres(-0)).toBe("0.00");
  });
});
