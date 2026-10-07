import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { checkScene } from "./checkScene";
import { SUPPORTED_SCHEMA_VERSION } from "./schemaVersion";

function example(): { entities: Record<string, unknown>[]; [key: string]: unknown } {
  return JSON.parse(
    readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
  );
}

describe("checking a scene before drawing it", () => {
  it("accepts the simulator's example scene", () => {
    const check = checkScene(example());

    expect(check.ok).toBe(true);
  });

  it("refuses an unknown kind of entity, saying where", () => {
    const scene = example();
    const entity = scene.entities[2];
    if (entity === undefined) {
      throw new Error("the example scene has fewer than three entities");
    }
    entity.kind = "TREE";

    const check = checkScene(scene);

    expect(check).toEqual({
      ok: false,
      problems: ["/entities/2/kind must be equal to one of the allowed values"],
    });
  });

  it("refuses an unknown shape", () => {
    const scene = example();
    const entity = scene.entities[2];
    if (entity === undefined) {
      throw new Error("the example scene has fewer than three entities");
    }
    entity.shape = { shape: "torus", radius: 1 };

    const check = checkScene(scene);

    expect(check.ok).toBe(false);
  });

  it("refuses a schema version it does not draw", () => {
    const check = checkScene({ ...example(), schema_version: SUPPORTED_SCHEMA_VERSION + 1 });

    expect(check).toEqual({
      ok: false,
      problems: [
        `schema version ${SUPPORTED_SCHEMA_VERSION + 1} is not the ${SUPPORTED_SCHEMA_VERSION} this viewer draws`,
      ],
    });
  });

  it("refuses something that is not a scene at all", () => {
    expect(checkScene(["not", "a", "scene"]).ok).toBe(false);
  });
});
