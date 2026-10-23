import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { CONTRACTS, generatedSources } from "../scripts/generateContractSources";

// The simulator's package, where each schema it publishes lies beside its
// model.
const PACKAGE = new URL("../../greenhouse_sim/", import.meta.url);
// The schemas of the files a scenario, or an installation, is written in,
// which the viewer does not read.
const NOT_READ = [
  "builder/installation.schema.json",
  "scenarios/layout.schema.json",
  "scenarios/scenario.schema.json",
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

  it("is generated from every schema the simulator publishes for it", () => {
    const published = readdirSync(PACKAGE, { recursive: true, encoding: "utf8" })
      .filter((path) => path.endsWith(".schema.json") && !NOT_READ.includes(path))
      .map((path) => `greenhouse_sim/${path}`);

    expect(CONTRACTS.map((contract) => contract.schemaPath).sort()).toEqual(published.sort());
  });
});
