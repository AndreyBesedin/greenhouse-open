// Generates the viewer's side of the scene contract from the schema the
// simulator publishes (greenhouse_sim/scene/snapshot.schema.json): the
// TypeScript types, and the schema itself as a module for validation.
//
//     npm run generate
//
// A Vitest test regenerates both and fails if the committed files differ.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { compile, type JSONSchema } from "json-schema-to-typescript";

const SCHEMA_FILE = new URL("../../greenhouse_sim/scene/snapshot.schema.json", import.meta.url);
export const TYPES_FILE = new URL("../src/scene/generated/snapshotTypes.ts", import.meta.url);
export const SCHEMA_MODULE_FILE = new URL(
  "../src/scene/generated/snapshotSchema.ts",
  import.meta.url,
);

const BANNER = [
  "// Generated from greenhouse_sim/scene/snapshot.schema.json by `npm run generate`.",
  "// Do not edit: change the simulator's types and regenerate.",
].join("\n");

export async function generatedSources(): Promise<{ types: string; schema: string }> {
  const schema: unknown = JSON.parse(readFileSync(SCHEMA_FILE, "utf8"));
  // The file is the simulator's published JSON Schema; the compiler checks it.
  const types = await compile(withoutPropertyTitles(schema) as JSONSchema, "SceneSnapshot", {
    bannerComment: BANNER,
    additionalProperties: false,
  });
  const schemaModule = `${BANNER}\n\nexport const SNAPSHOT_SCHEMA = ${JSON.stringify(schema, null, 2)};\n`;
  return { types, schema: schemaModule };
}

// Pydantic titles every property, which would give each one its own type
// alias (`X`, `X1`, `Shape2`...). Only the named definitions need titles.
function withoutPropertyTitles(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(withoutPropertyTitles);
  }
  if (typeof value !== "object" || value === null) {
    return value;
  }
  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (key === "properties" && typeof item === "object" && item !== null) {
      result[key] = Object.fromEntries(
        Object.entries(item).map(([name, property]) => {
          const { title: _, ...rest } = property as Record<string, unknown>;
          return [name, withoutPropertyTitles(rest)];
        }),
      );
    } else {
      result[key] = withoutPropertyTitles(item);
    }
  }
  return result;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const sources = await generatedSources();
  writeFileSync(TYPES_FILE, sources.types);
  writeFileSync(SCHEMA_MODULE_FILE, sources.schema);
  console.log("wrote the scene types and schema module");
}
