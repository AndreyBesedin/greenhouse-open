import { describe, expect, it } from "vitest";
import { arrowSpacing, fieldArrows, MATRIX_SIZE, MAX_ARROWS } from "./arrows";
import { sliceFrom, sliceText } from "./display";
import { defaultSlice, quantityScale, sliceQuantities } from "./drawing";
import { drawnPoints, STEPS_PER_SEGMENT, streamlineGeometry } from "./FieldStreamlines";
import type { Channel, EnvironmentField } from "./field";
import { sliceExtent, sliceSpans, sliceValues } from "./slice";
import { MAX_SEEDS, SEED_EVERY_CELLS, seedSpacing, streamlines } from "./streamlines";

const SIZE = 0.5;

/** A field over a box `cells` cells wide, of SIZE, whose velocity and
 * temperature at each centre are given by functions of position. */
function analytic(
  cells: { x: number; y: number; z: number },
  velocity: (x: number, y: number, z: number) => [number, number, number],
  temperature: (x: number, y: number, z: number) => number,
): EnvironmentField {
  const count = cells.x * cells.y * cells.z;
  const vectors = new Float32Array(count * 3);
  const scalars = new Float32Array(count);
  let index = 0;
  for (let k = 0; k < cells.z; k += 1) {
    for (let j = 0; j < cells.y; j += 1) {
      for (let i = 0; i < cells.x; i += 1) {
        const [x, y, z] = [(i + 0.5) * SIZE, (j + 0.5) * SIZE, (k + 0.5) * SIZE];
        vectors.set(velocity(x, y, z), index * 3);
        scalars[index] = temperature(x, y, z);
        index += 1;
      }
    }
  }
  const velocityChannel: Channel = {
    quantity: "velocity",
    unit: "m/s",
    components: 3,
    values: vectors,
    minimum: 0,
    maximum: 1,
  };
  const temperatureChannel: Channel = {
    quantity: "temperature",
    unit: "°C",
    components: 1,
    values: scalars,
    minimum: 15,
    maximum: 25,
  };
  return {
    fieldId: "test",
    source: "test",
    grid: { origin: { x: 0, y: 0, z: 0 }, cell_size: { x: SIZE, y: SIZE, z: SIZE }, cells },
    channels: { velocity: velocityChannel, temperature: temperatureChannel },
  };
}

// A vortex turning about the vertical line through (5, 5): every streamline
// is a circle about it.
const VORTEX = analytic(
  { x: 20, y: 20, z: 3 },
  (x, y) => [-(y - 5), x - 5, 0],
  () => 20,
);
// A uniform breeze along +x.
const BREEZE = analytic(
  { x: 12, y: 6, z: 3 },
  () => [0.5, 0, 0],
  (x, _, z) => 15 + 2 * z + 0.25 * x,
);

describe("streamlines", () => {
  it("circle a vortex's centre at their seed's distance, and close", () => {
    const lines = streamlines(VORTEX, VORTEX.channels.velocity as Channel);
    // Circles that fit inside the field, which is 10 by 10 m about (5, 5).
    const around = lines.filter((line) => {
      const [first] = line.points;
      const radius = first === undefined ? 0 : Math.hypot(first.x - 5, first.y - 5);
      return radius > 1 && radius < 4;
    });

    expect(around.length).toBeGreaterThan(0);
    for (const line of around.slice(0, 10)) {
      const radii = line.points.map((p) => Math.hypot(p.x - 5, p.y - 5));
      const first = line.points[0];
      const last = line.points[line.points.length - 1];
      if (first === undefined || last === undefined) {
        throw new Error("a streamline has points");
      }
      // Closed, round, and level.
      expect(Math.hypot(last.x - first.x, last.y - first.y)).toBeLessThan(0.3);
      expect(Math.max(...radii) - Math.min(...radii)).toBeLessThan(0.02 * Math.max(...radii));
      expect(new Set(line.points.map((p) => p.z.toFixed(6))).size).toBe(1);
    }
  });

  it("run straight down a breeze, from one face of the field to the other", () => {
    const lines = streamlines(BREEZE, BREEZE.channels.velocity as Channel);
    const [line] = lines;
    if (line === undefined) {
      throw new Error("the breeze has streamlines");
    }
    const xs = line.points.map((p) => p.x);

    expect(new Set(line.points.map((p) => p.y)).size).toBe(1);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
    expect(Math.min(...xs)).toBeLessThan(0.3);
    expect(Math.max(...xs)).toBeGreaterThan(12 * SIZE - 0.3);
    expect(line.speeds.every((speed) => Math.abs(speed - 0.5) < 1e-6)).toBe(true);
  });
});

describe("streamlines as they are drawn", () => {
  it("run through every second step, and the last", () => {
    expect(drawnPoints(0)).toEqual([]);
    expect(drawnPoints(1)).toEqual([0]);
    expect(drawnPoints(5)).toEqual([0, 2, 4]);
    expect(drawnPoints(6)).toEqual([0, 2, 4, 5]);
  });

  it("make a segment of every second step, from one end of the line to the other", () => {
    const channel = BREEZE.channels.velocity as Channel;
    const lines = streamlines(BREEZE, channel);
    const geometry = streamlineGeometry(BREEZE, channel, { min: 0, max: 1 });
    const segments = lines.reduce(
      (sum, line) => sum + Math.ceil((line.points.length - 1) / STEPS_PER_SEGMENT),
      0,
    );
    const xs = Array.from(geometry.getAttribute("position").array).filter((_, i) => i % 3 === 0);

    expect(geometry.getAttribute("position").count).toBe(2 * segments);
    expect(Math.min(...xs)).toBeLessThan(0.3);
    expect(Math.max(...xs)).toBeGreaterThan(12 * SIZE - 0.3);
  });
});

describe("a field's arrows on a big field", () => {
  it("stand every cell on a small one, and every few along x and y on a big one", () => {
    // The airflow box's and the climate box's fields: every cell.
    expect(arrowSpacing({ x: 24, y: 13, z: 6 })).toBe(1);
    expect(arrowSpacing({ x: 24, y: 13, z: 8 })).toBe(1);
    // The tomato compartment's, 48 by 32 by 12 cells: every second, 4608.
    expect(arrowSpacing({ x: 48, y: 32, z: 12 })).toBe(2);
    // However tall, it stops at one arrow a layer.
    expect(arrowSpacing({ x: 2, y: 2, z: MAX_ARROWS + 1 })).toBe(2);
  });

  it("are no more than the most a field draws", () => {
    const big = analytic(
      { x: 48, y: 32, z: 12 },
      () => [0.5, 0, 0],
      () => 20,
    );
    const arrows = fieldArrows(big, big.channels.velocity as Channel);

    expect(arrows.matrices.length / MATRIX_SIZE).toBe(24 * 16 * 12);
    expect(arrows.matrices.length / MATRIX_SIZE).toBeLessThanOrEqual(MAX_ARROWS);
  });
});

describe("streamlines' seeds", () => {
  it("start every few cells, and spread out in a field too big for more", () => {
    // gh_001's old field: every third cell.
    expect(seedSpacing({ x: 16, y: 20, z: 7 })).toBe(SEED_EVERY_CELLS);
    // The tomato compartment's, 48 by 32 by 12 cells: every fourth, 288 seeds.
    expect(seedSpacing({ x: 48, y: 32, z: 12 })).toBe(4);
    const big = { x: 200, y: 100, z: 20 };
    const every = seedSpacing(big);
    expect(
      Math.ceil(big.x / every) * Math.ceil(big.y / every) * Math.ceil(big.z / every),
    ).toBeLessThanOrEqual(MAX_SEEDS);
  });
});

describe("a slice through a field", () => {
  it("holds a linear field's exact values at the cells' corners across it", () => {
    const slice = sliceValues(BREEZE, "temperature", "z", 0.75);

    expect([slice.columns, slice.rows]).toEqual([13, 7]);
    slice.points.forEach((point, index) => {
      // Inside the outermost centres, trilinear interpolation is exact.
      if (point.x >= 0.25 && point.x <= 5.75) {
        expect(slice.values[index]).toBeCloseTo(15 + 2 * 0.75 + 0.25 * point.x, 4);
      }
    });
  });

  it("spans the two other axes, and lies within the field along its own", () => {
    const speed = sliceValues(BREEZE, "speed", "x", 2);

    expect(sliceSpans("x")).toEqual(["y", "z"]);
    expect(sliceSpans("z")).toEqual(["x", "y"]);
    expect(speed.points.every((point) => point.x === 2)).toBe(true);
    expect(speed.values.every((value) => value !== null && Math.abs(value - 0.5) < 1e-6)).toBe(
      true,
    );
    expect(sliceExtent(BREEZE.grid, "z")).toEqual({ min: 0, max: 1.5 });
  });

  it("is drawn by default across the field's middle height, by its first scalar", () => {
    expect(sliceQuantities(BREEZE)).toEqual(["speed", "temperature"]);
    expect(defaultSlice(BREEZE)).toEqual({ quantity: "temperature", axis: "z", position: 0.75 });
    expect(quantityScale(BREEZE, "speed")).toEqual({
      title: "air speed",
      unit: "m/s",
      range: { min: 0, max: 1 },
    });
    expect(quantityScale(BREEZE, "co2")).toBeNull();
  });

  it("is kept in the address as quantity:axis:position", () => {
    const slice = { quantity: "temperature", axis: "y", position: 2.5 } as const;

    expect(sliceFrom(sliceText(slice))).toEqual(slice);
    expect(sliceFrom("temperature:w:1")).toBeUndefined();
    expect(sliceFrom("wind:z:1")).toBeUndefined();
    expect(sliceFrom("speed:z:")).toBeUndefined();
  });
});
