import { describe, expect, it } from "vitest";

import {
  formatCount,
  formatFrameTime,
  formatMemory,
  formatMetres,
  formatPoint,
  formatSize,
  framesPerSecond,
} from "./readouts";

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

  it("writes a size to the centimetre, or finer if it is under one", () => {
    expect(formatSize(0.0018)).toBe("0.0018");
    expect(formatSize(0.002)).toBe("0.0020");
    expect(formatSize(0.02)).toBe("0.02");
    expect(formatSize(12.5)).toBe("12.50");
  });
});

describe("the renderer's diagnostics", () => {
  it("writes frame times to a tenth of a millisecond", () => {
    expect(formatFrameTime(16.666, 33.33)).toBe("16.7 ms, worst 33.3 ms");
  });

  it("separates thousands in counts", () => {
    expect(formatCount(9_600_002)).toBe("9,600,002");
  });

  it("adds the heap only where the browser reports it", () => {
    expect(formatMemory(5, 1, null)).toBe("5 geometries, 1 textures");
    expect(formatMemory(5, 1, 10 * 1_048_576)).toBe("5 geometries, 1 textures, 10 MiB heap");
  });
});
