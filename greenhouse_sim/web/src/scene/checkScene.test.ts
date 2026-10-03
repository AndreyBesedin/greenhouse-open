import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  generatedSources,
  SCHEMA_MODULE_FILE,
  TYPES_FILE,
} from "../../scripts/generateSceneSources";
import { checkScene } from "./checkScene";

function example(): { entities: Record<string, unknown>[]; [key: string]: unknown } {
  return JSON.parse(
    readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
  );
}

describe("the viewer's side of the scene contract", () => {
  it("is generated from the schema the simulator publishes, and up to date", async () => {
    const sources = await generatedSources();

    expect(readFileSync(TYPES_FILE, "utf8")).toBe(sources.types);
    expect(readFileSync(SCHEMA_MODULE_FILE, "utf8")).toBe(sources.schema);
  });
});

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
    const check = checkScene({ ...example(), schema_version: 2 });

    expect(check).toEqual({
      ok: false,
      problems: ["schema version 2 is not the 1 this viewer draws"],
    });
  });

  it("refuses something that is not a scene at all", () => {
    expect(checkScene(["not", "a", "scene"]).ok).toBe(false);
  });
});
