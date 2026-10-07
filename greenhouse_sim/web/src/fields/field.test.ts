import { Matrix4, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { fieldArrows, MATRIX_SIZE } from "./arrows";
import { checkField, sample } from "./field";
import type { FieldDocument } from "./generated/fieldTypes";
import { fieldUrl, loadField } from "./source";

// The simulator's shear over a box 2 by 1 by 1 m in cells of 0.5 m: the air
// moves along x at 0.25 (m/s)/m of height, and warms 1.2 °C a metre up and
// 0.1 °C a metre along (`greenhouse_sim/fields/synthetic.py`).
const CELLS = { x: 4, y: 2, z: 2 };
const SIZE = 0.5;

function centre(index: number): number {
  return (index + 0.5) * SIZE;
}

function encoded(values: number[]): string {
  const bytes = new Uint8Array(Float32Array.from(values).buffer);
  return btoa(String.fromCharCode(...bytes));
}

function shearDocument(): FieldDocument {
  const velocity: number[] = [];
  const temperature: number[] = [];
  for (let k = 0; k < CELLS.z; k += 1) {
    for (let j = 0; j < CELLS.y; j += 1) {
      for (let i = 0; i < CELLS.x; i += 1) {
        velocity.push(0.25 * centre(k), 0, 0);
        temperature.push(18 + 1.2 * centre(k) + 0.1 * centre(i));
      }
    }
  }
  return {
    schema_version: 1,
    field_id: "box_shear",
    source: "synthetic:shear",
    time_s: 0,
    grid: {
      origin: { x: 0, y: 0, z: 0 },
      cell_size: { x: SIZE, y: SIZE, z: SIZE },
      cells: CELLS,
    },
    channels: [
      {
        quantity: "velocity",
        unit: "m/s",
        components: 3,
        encoding: "float32-le-base64",
        data: encoded(velocity),
        minimum: 0.0625,
        maximum: 0.1875,
      },
      {
        quantity: "temperature",
        unit: "°C",
        components: 1,
        encoding: "float32-le-base64",
        data: encoded(temperature),
        minimum: 18.325,
        maximum: 19.075,
      },
    ],
  };
}

function loaded() {
  const check = checkField(shearDocument());
  if (!check.ok) {
    throw new Error(check.problems.join("; "));
  }
  return check.field;
}

describe("a published field", () => {
  it("is checked against the simulator's schema, and decoded", () => {
    const field = loaded();

    expect(field.channels.velocity?.values).toHaveLength(4 * 2 * 2 * 3);
    expect(field.channels.temperature?.unit).toBe("°C");
  });

  it("is refused if it breaks the schema, or holds the wrong number of values", () => {
    const missing = checkField({ ...shearDocument(), grid: undefined });
    const short = shearDocument();
    const [velocity] = short.channels;
    if (velocity !== undefined) {
      velocity.data = encoded([1, 2, 3]);
    }

    expect(missing.ok).toBe(false);
    expect(checkField(short)).toEqual({ ok: false, problems: ["velocity has 3 values, not 48"] });
  });

  it("is sampled as the simulator samples it: exactly, for a linear field", () => {
    const field = loaded();
    const temperature = field.channels.temperature;
    const velocity = field.channels.velocity;
    if (temperature === undefined || velocity === undefined) {
      throw new Error("the shear has its channels");
    }
    const point = { x: 1.1, y: 0.6, z: 0.6 };

    expect(sample(field.grid, temperature, point)?.[0]).toBeCloseTo(18 + 1.2 * 0.6 + 0.1 * 1.1, 5);
    expect(sample(field.grid, velocity, point)).toEqual([expect.closeTo(0.15, 5), 0, 0]);
    // Out to the faces, the outermost centres' values; outside, nothing.
    expect(sample(field.grid, temperature, { x: 1.1, y: 0.6, z: 0.05 })?.[0]).toBeCloseTo(
      18 + 1.2 * 0.25 + 0.1 * 1.1,
      5,
    );
    expect(sample(field.grid, temperature, { x: 2.01, y: 0.5, z: 0.5 })).toBeNull();
  });

  it("is loaded from the simulator for a scenario, and an error becomes a state", async () => {
    const asked: string[] = [];
    const state = await loadField("gh_001", "shear", async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify(shearDocument()), { status: 200 });
    });
    const missing = await loadField(
      "gh_001",
      "wind",
      async () => new Response("", { status: 404 }),
    );
    const newer = await loadField(
      "gh_001",
      "shear",
      async () =>
        new Response(JSON.stringify({ ...shearDocument(), schema_version: 2 }), { status: 200 }),
    );

    expect(asked).toEqual([fieldUrl("gh_001", "shear")]);
    expect(state.status).toBe("loaded");
    expect(missing).toEqual({ status: "unavailable", reason: "the simulator API answered 404" });
    expect(newer.status).toBe("rejected");
  });
});

describe("a field's arrows", () => {
  it("stand at every cell, point where the air goes, and grow with its speed", () => {
    const field = loaded();
    const velocity = field.channels.velocity;
    if (velocity === undefined) {
      throw new Error("the shear has its velocity");
    }
    const arrows = fieldArrows(field, velocity);
    const first = new Matrix4().fromArray(arrows.matrices, 0);
    const last = new Matrix4().fromArray(arrows.matrices, arrows.matrices.length - MATRIX_SIZE);
    const tip = (matrix: Matrix4) => new Vector3(0, 0, 1).applyMatrix4(matrix);
    const base = (matrix: Matrix4) => new Vector3(0, 0, 0).applyMatrix4(matrix);

    expect(arrows.matrices).toHaveLength(16 * MATRIX_SIZE);
    // The lowest arrow points along +x, centred on its cell's centre.
    const low = tip(first).sub(base(first));
    expect(low.x).toBeGreaterThan(0);
    expect(low.y).toBeCloseTo(0);
    expect(low.z).toBeCloseTo(0);
    expect((tip(first).x + base(first).x) / 2).toBeCloseTo(0.25);
    // The highest is three times as fast, and as long, at 90% of a cell.
    const high = tip(last).sub(base(last));
    expect(high.length()).toBeCloseTo(0.9 * SIZE);
    expect(high.length()).toBeCloseTo(3 * low.length());
    expect(arrows.colors[0]).not.toEqual(arrows.colors[arrows.colors.length - 1]);
  });
});
