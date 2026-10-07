import { describe, expect, it } from "vitest";
import { differenceText, readingText } from "./FieldProbes";
import { checkField } from "./field";
import type { FieldDocument } from "./generated/fieldTypes";
import {
  difference,
  MAX_PROBES,
  middleOf,
  probeOverlays,
  probesFrom,
  probesText,
  readingAt,
} from "./probes";

function encode(values: number[]): string {
  const bytes = new Uint8Array(Float32Array.from(values).buffer);
  return btoa(String.fromCharCode(...bytes));
}

// A box 2 by 1 by 1 m of two cells along x: the air along x, 0.2 m/s in the
// first cell and 0.6 m/s in the second, and its temperature or pressure.
function twoCells(scalar: "temperature" | "pressure", values: [number, number]) {
  const document: FieldDocument = {
    schema_version: 1,
    field_id: `two_${scalar}`,
    source: "test",
    time_s: 0,
    grid: {
      origin: { x: 0, y: 0, z: 0 },
      cell_size: { x: 1, y: 1, z: 1 },
      cells: { x: 2, y: 1, z: 1 },
    },
    channels: [
      {
        quantity: "velocity",
        unit: "m/s",
        components: 3,
        encoding: "float32-le-base64",
        data: encode([0.2, 0, 0, 0.6, 0, 0]),
        minimum: 0.2,
        maximum: 0.6,
      },
      {
        quantity: scalar,
        unit: scalar === "temperature" ? "°C" : "Pa",
        components: 1,
        encoding: "float32-le-base64",
        data: encode(values),
        minimum: Math.min(...values),
        maximum: Math.max(...values),
      },
    ],
  };
  const check = checkField(document);
  if (!check.ok) {
    throw new Error(check.problems.join("; "));
  }
  return check.field;
}

describe("probes", () => {
  it("are kept in the address as x:y:z, one after another", () => {
    const probes = [
      { x: 3, y: 3.2, z: 0.75 },
      { x: 7, y: 3.2, z: 0.75 },
    ];

    expect(probesText(probes)).toBe("3:3.2:0.75,7:3.2:0.75");
    expect(probesFrom("3:3.2:0.75,7:3.2:0.75")).toEqual(probes);
    expect(probesFrom("3:3.2")).toBeUndefined();
    expect(probesFrom("3:x:1")).toBeUndefined();
    expect(probesFrom("")).toBeUndefined();
    const many = Array.from({ length: MAX_PROBES + 2 }, () => "1:1:1").join(",");
    expect(probesFrom(many)).toHaveLength(MAX_PROBES);
  });

  it("read a field as the simulator samples it, and nothing outside it", () => {
    const field = twoCells("temperature", [18, 22]);

    // Halfway between the cells' centres: their mean.
    const between = readingAt(field, { x: 1, y: 0.5, z: 0.5 });
    expect(between.velocity?.x).toBeCloseTo(0.4);
    expect(between.speed).toBeCloseTo(0.4);
    expect(between.scalars.temperature).toBeCloseTo(20);
    expect(readingAt(field, { x: 2.5, y: 0.5, z: 0.5 })).toEqual({
      velocity: null,
      speed: null,
      scalars: {},
    });
    expect(middleOf(field)).toEqual({ x: 1, y: 0.5, z: 0.5 });
  });

  it("compare two fields' readings: speed, turn and the scalars both hold", () => {
    const along = twoCells("pressure", [0.2, 0.1]);
    const across = twoCells("temperature", [20, 20]);
    const a = readingAt(along, { x: 0.5, y: 0.5, z: 0.5 });
    const turned = { ...a, velocity: { x: 0, y: 0.2, z: 0 } };
    const warmer = { ...a, scalars: { pressure: 0.5 } };

    expect(difference(a, readingAt(across, { x: 1.5, y: 0.5, z: 0.5 }))).toEqual({
      speed: expect.closeTo(-0.4),
      turnDeg: 0,
      scalars: {},
    });
    expect(difference(turned, a).turnDeg).toBeCloseTo(90);
    expect(difference(warmer, a).scalars.pressure).toBeCloseTo(0.3);
    expect(difference(a, readingAt(across, { x: 9, y: 0, z: 0 }))).toEqual({
      speed: null,
      turnDeg: null,
      scalars: {},
    });
  });

  it("are written out with their units, and marked in the view", () => {
    const field = twoCells("pressure", [0.2, 0.1]);
    const reading = readingAt(field, { x: 0.5, y: 0.5, z: 0.5 });
    const other = { ...reading, speed: 0.1, velocity: { x: 0.1, y: 0, z: 0 } };

    expect(readingText(field, reading)).toBe("0.20 m/s (0.20, 0.00, 0.00), pressure 0.20 Pa");
    expect(readingText(field, readingAt(field, { x: 5, y: 0, z: 0 }))).toBe("outside the field");
    expect(differenceText(field, difference(reading, other))).toBe(
      "+0.10 m/s, turned 0.00°, pressure 0.00 Pa",
    );
    const marks = probeOverlays([{ x: 1.5, y: 0.5, z: 0.5 }], field);
    expect(marks.map((mark) => mark.kind)).toEqual(["line", "point", "label", "arrow"]);
    // The fastest air's arrow is a metre long.
    expect(marks[3]).toMatchObject({ length: expect.closeTo(1) });
  });
});
