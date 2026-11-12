import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  asTheViewerChecksIt,
  CONTRACTS,
  generatedSources,
  PROTOCOL,
} from "../scripts/generateContractSources";

// The simulator's package, where each schema it publishes lies beside its
// model.
const PACKAGE = new URL("../../greenhouse_sim/", import.meta.url);
// The schemas of the files a scenario, or an installation, is written in,
// and of a crop model's parameters and parameter sets, which the viewer
// does not read: a parameter set's form will, through the answers that
// serve them (P20.5).
const NOT_READ = [
  "builder/installation.schema.json",
  "scenarios/layout.schema.json",
  "scenarios/scenario.schema.json",
  "biology/tomato/tomgro/parameters.schema.json",
  "biology/tomato/vanthoor/parameters.schema.json",
  "biology/parameter_set.schema.json",
];

describe("the viewer's side of the simulator's contracts", () => {
  it.each(CONTRACTS.map((contract) => [contract.schemaPath, contract] as const))(
    "is generated from %s, and up to date",
    async (_, contract) => {
      const sources = await generatedSources(contract);

      expect(readFileSync(contract.typesFile, "utf8")).toBe(sources.types);
      expect(readFileSync(contract.schemaModuleFile, "utf8")).toBe(sources.schema);
    },
  );

  it("checks answers without the descriptions meant for people, and keeps a field called one", () => {
    const published = {
      description: "For people.",
      properties: {
        description: { description: "Also for people.", type: "string" },
        items: { items: [{ description: "So is this.", type: "number" }] },
      },
      $defs: { description: { description: "And this.", const: 1 } },
    };

    expect(asTheViewerChecksIt(published)).toEqual({
      properties: {
        description: { type: "string" },
        items: { items: [{ type: "number" }] },
      },
      $defs: { description: { const: 1 } },
    });
  });

  it("is generated from every schema the simulator publishes for it", () => {
    const published = readdirSync(PACKAGE, { recursive: true, encoding: "utf8" })
      .filter((path) => path.endsWith(".schema.json") && !NOT_READ.includes(path))
      .map((path) => `greenhouse_sim/${path}`);

    const simulators = CONTRACTS.map((contract) => contract.schemaPath).filter(
      (path) => !path.startsWith(PROTOCOL),
    );
    expect(simulators.sort()).toEqual(published.sort());
  });
});
