import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { CONTRACTS, generatedSources } from "../scripts/generateContractSources";

describe("the viewer's side of the simulator's contracts", () => {
  it.each(CONTRACTS.map((contract) => [contract.schemaPath, contract] as const))(
    "is generated from %s, and up to date",
    async (_, contract) => {
      const sources = await generatedSources(contract);

      expect(readFileSync(contract.typesFile, "utf8")).toBe(sources.types);
      expect(readFileSync(contract.schemaModuleFile, "utf8")).toBe(sources.schema);
    },
  );
});
