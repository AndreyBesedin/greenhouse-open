// Generates the viewer's side of the simulator's contracts from the schemas
// it publishes: the scene (greenhouse_sim/scene/snapshot.schema.json) and the
// environment field (greenhouse_sim/fields/field.schema.json). For each, the
// TypeScript types, and the schema itself as a module for validation.
//
//     npm run generate
//
// Vitest tests regenerate them and fail if the committed files differ.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { compile, type JSONSchema } from "json-schema-to-typescript";

/** One contract the simulator publishes, and where its viewer side goes. */
export interface Contract {
  /** The schema, as the simulator publishes it. */
  schemaFile: URL;
  /** Its path in the repository, for the generated files' banner. */
  schemaPath: string;
  /** The schema's root type. */
  rootType: string;
  typesFile: URL;
  schemaModuleFile: URL;
  /** The name the schema module exports the schema under. */
  schemaConstant: string;
}

export const SCENE_CONTRACT: Contract = {
  schemaFile: new URL("../../greenhouse_sim/scene/snapshot.schema.json", import.meta.url),
  schemaPath: "greenhouse_sim/scene/snapshot.schema.json",
  rootType: "SceneSnapshot",
  typesFile: new URL("../src/scene/generated/snapshotTypes.ts", import.meta.url),
  schemaModuleFile: new URL("../src/scene/generated/snapshotSchema.ts", import.meta.url),
  schemaConstant: "SNAPSHOT_SCHEMA",
};

export const FIELD_CONTRACT: Contract = {
  schemaFile: new URL("../../greenhouse_sim/fields/field.schema.json", import.meta.url),
  schemaPath: "greenhouse_sim/fields/field.schema.json",
  rootType: "FieldDocument",
  typesFile: new URL("../src/fields/generated/fieldTypes.ts", import.meta.url),
  schemaModuleFile: new URL("../src/fields/generated/fieldSchema.ts", import.meta.url),
  schemaConstant: "FIELD_SCHEMA",
};

export const CONTRACTS: readonly Contract[] = [SCENE_CONTRACT, FIELD_CONTRACT];

export async function generatedSources(
  contract: Contract,
): Promise<{ types: string; schema: string }> {
  const banner = [
    `// Generated from ${contract.schemaPath} by \`npm run generate\`.`,
    "// Do not edit: change the simulator's types and regenerate.",
  ].join("\n");
  const schema: unknown = JSON.parse(readFileSync(contract.schemaFile, "utf8"));
  // The file is the simulator's published JSON Schema; the compiler checks it.
  const types = await compile(withoutPropertyTitles(schema) as JSONSchema, contract.rootType, {
    bannerComment: banner,
    additionalProperties: false,
  });
  const schemaModule = `${banner}\n\nexport const ${contract.schemaConstant} = ${JSON.stringify(schema, null, 2)};\n`;
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
  for (const contract of CONTRACTS) {
    const sources = await generatedSources(contract);
    mkdirSync(new URL(".", contract.typesFile), { recursive: true });
    writeFileSync(contract.typesFile, sources.types);
    writeFileSync(contract.schemaModuleFile, sources.schema);
    console.log(`wrote the types and schema module for ${contract.schemaPath}`);
  }
}
