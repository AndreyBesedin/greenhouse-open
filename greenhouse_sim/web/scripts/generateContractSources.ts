// Generates the viewer's side of the simulator's contracts from the schemas
// it publishes (`tests/test_published_schemas.py` lists them): the scene,
// the environment field, the CFD geometry, and each service's answer the
// viewer reads. For each, the TypeScript types, and the schema itself as a
// module for validation, in its area's `generated` folder.
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

/** The contract published at `schemaPath`, under `greenhouse_sim/`, whose
 * viewer side is `<folder>/generated/<name>Types.ts` and `<name>Schema.ts`,
 * the folder of the module that reads it. */
function contract(
  schemaPath: string,
  rootType: string,
  [folder, name]: [string, string],
  schemaConstant: string,
): Contract {
  return {
    schemaFile: new URL(`../../${schemaPath}`, import.meta.url),
    schemaPath,
    rootType,
    typesFile: new URL(`../${folder}/generated/${name}Types.ts`, import.meta.url),
    schemaModuleFile: new URL(`../${folder}/generated/${name}Schema.ts`, import.meta.url),
    schemaConstant,
  };
}

const SERVICES = "greenhouse_sim/services";
const CLIMATE = "greenhouse_sim/climate";

export const CONTRACTS: readonly Contract[] = [
  contract(
    "greenhouse_sim/scene/snapshot.schema.json",
    "SceneSnapshot",
    ["src/scene", "snapshot"],
    "SNAPSHOT_SCHEMA",
  ),
  contract(
    "greenhouse_sim/fields/field.schema.json",
    "FieldDocument",
    ["src/fields", "field"],
    "FIELD_SCHEMA",
  ),
  contract(
    "greenhouse_sim/cfd/geometry.schema.json",
    "CfdGeometry",
    ["src/cfd", "geometry"],
    "CFD_GEOMETRY_SCHEMA",
  ),
  contract(
    `${SERVICES}/version.schema.json`,
    "Version",
    ["src/qaMode", "version"],
    "VERSION_SCHEMA",
  ),
  contract(
    `${SERVICES}/scenario_summary.schema.json`,
    "ScenarioSummary",
    ["src", "scenarioSummary"],
    "SCENARIO_SUMMARY_SCHEMA",
  ),
  contract(
    `${SERVICES}/run_manifest.schema.json`,
    "RunManifest",
    ["src/qaMode", "runManifest"],
    "RUN_MANIFEST_SCHEMA",
  ),
  contract(
    `${SERVICES}/run_state.schema.json`,
    "RunState",
    ["src/qaMode", "runState"],
    "RUN_STATE_SCHEMA",
  ),
  contract(
    `${SERVICES}/observations.schema.json`,
    "SensorObservations",
    ["src/sensors", "observations"],
    "OBSERVATIONS_SCHEMA",
  ),
  contract(
    `${SERVICES}/truth.schema.json`,
    "SensorTruths",
    ["src/sensors", "truth"],
    "TRUTH_SCHEMA",
  ),
  contract(
    `${SERVICES}/weather.schema.json`,
    "WeatherAtAMoment",
    ["src/weather", "weather"],
    "WEATHER_SCHEMA",
  ),
  contract(
    `${SERVICES}/weather_day.schema.json`,
    "WeatherThroughADay",
    ["src/weather", "weatherDay"],
    "WEATHER_DAY_SCHEMA",
  ),
  contract(
    `${SERVICES}/equipment.schema.json`,
    "EquipmentAt",
    ["src/scene", "equipment"],
    "EQUIPMENT_SCHEMA",
  ),
  contract(
    `${SERVICES}/field_names.schema.json`,
    "FieldNames",
    ["src/fields", "fieldNames"],
    "FIELD_NAMES_SCHEMA",
  ),
  contract(
    `${SERVICES}/timeline.schema.json`,
    "TimelineDocument",
    ["src/timeline", "timeline"],
    "TIMELINE_SCHEMA",
  ),
  contract(
    `${SERVICES}/checkpoint.schema.json`,
    "CheckpointSummary",
    ["src/checkpoints", "checkpoint"],
    "CHECKPOINT_SCHEMA",
  ),
  contract(
    `${SERVICES}/playback.schema.json`,
    "PlaybackState",
    ["src/scene", "playback"],
    "PLAYBACK_SCHEMA",
  ),
  contract(`${SERVICES}/live.schema.json`, "LiveState", ["src/scene", "live"], "LIVE_SCHEMA"),
  contract(
    `${SERVICES}/plants_light.schema.json`,
    "PlantsLight",
    ["src/plants", "plantsLight"],
    "PLANTS_LIGHT_SCHEMA",
  ),
  contract(
    `${SERVICES}/crop_plant.schema.json`,
    "CropPlant",
    ["src/plants", "cropPlant"],
    "CROP_PLANT_SCHEMA",
  ),
  contract(
    `${SERVICES}/lab_checks.schema.json`,
    "LabChecks",
    ["src/plants", "labChecks"],
    "LAB_CHECKS_SCHEMA",
  ),
  contract(
    `${SERVICES}/lab_environments.schema.json`,
    "LabEnvironments",
    ["src/plants", "labEnvironments"],
    "LAB_ENVIRONMENTS_SCHEMA",
  ),
  // The setup builder's (P12.2).
  contract(
    "greenhouse_sim/builder/basic.schema.json",
    "BasicSetup",
    ["src/builder", "basic"],
    "BASIC_SETUP_SCHEMA",
  ),
  contract(
    `${SERVICES}/builder.schema.json`,
    "Assessed",
    ["src/builder", "assessed"],
    "ASSESSED_SCHEMA",
  ),
  contract(
    `${SERVICES}/drafts.schema.json`,
    "DraftsListed",
    ["src/builder", "drafts"],
    "DRAFTS_SCHEMA",
  ),
  contract(
    "greenhouse_sim/biology/tomato/organ/plant.schema.json",
    "Plant",
    ["src/plants", "plant"],
    "PLANT_SCHEMA",
  ),
  contract(
    `${CLIMATE}/house.schema.json`,
    "HouseTrace",
    ["src/fields", "houseAir"],
    "HOUSE_AIR_SCHEMA",
  ),
  contract(
    `${CLIMATE}/probes.schema.json`,
    "ClimateProbes",
    ["src/fields", "probes"],
    "CLIMATE_PROBES_SCHEMA",
  ),
  contract(
    `${CLIMATE}/glazing.schema.json`,
    "GlazingAt",
    ["src/fields", "glazing"],
    "GLAZING_SCHEMA",
  ),
  contract(
    `${CLIMATE}/openings.schema.json`,
    "OpeningsAt",
    ["src/fields", "openings"],
    "OPENINGS_SCHEMA",
  ),
];

export async function generatedSources(
  contract: Contract,
): Promise<{ types: string; schema: string }> {
  const banner = [
    `// Generated from ${contract.schemaPath} by \`npm run generate\`.`,
    "// Do not edit: change the simulator's types and regenerate.",
  ].join("\n");
  const schema: unknown = JSON.parse(readFileSync(contract.schemaFile, "utf8"));
  // The file is the simulator's published JSON Schema; the compiler checks it.
  const types = await compile(asTheCompilerReadsIt(schema) as JSONSchema, contract.rootType, {
    bannerComment: banner,
    additionalProperties: false,
  });
  const schemaModule = `${banner}\n\nexport const ${contract.schemaConstant} = ${JSON.stringify(schema, null, 2)};\n`;
  return { types, schema: schemaModule };
}

// The schema as the types' compiler reads it. Pydantic titles every
// property, which would give each one its own type alias (`X`, `X1`,
// `Shape2`...); only the named definitions need titles. And the compiler
// reads a tuple's items in draft 07's form, `items` as a list, not 2020-12's
// `prefixItems`, which the schema module keeps for validation.
function asTheCompilerReadsIt(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(asTheCompilerReadsIt);
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
          return [name, asTheCompilerReadsIt(rest)];
        }),
      );
    } else {
      result[key === "prefixItems" ? "items" : key] = asTheCompilerReadsIt(item);
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
