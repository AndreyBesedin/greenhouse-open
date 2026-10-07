import { describe, expect, it } from "vitest";

import { labChecks, loadLabChecks } from "./checks";

describe("the lab's checks", () => {
  it("say, by plant, what is wrong, and nothing where all is well", () => {
    const body = { day: 12, problems: { p01: [], p02: ["p02_n03 is gone"] } };

    expect(labChecks(body)).toEqual(body);
  });

  it("are refused when they cannot be read", () => {
    expect(() => labChecks([])).toThrow("no day or no problems");
    expect(() => labChecks({ day: 1, problems: { p01: [3] } })).toThrow(
      "p01's problems are not a list of text",
    );
  });

  it("are asked for by run, and an error becomes unavailable", async () => {
    const asked: string[] = [];
    const loaded = await loadLabChecks("day=3&seed=1&environment=reference", async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify({ day: 3, problems: { p01: [] } }), { status: 200 });
    });
    const refused = await loadLabChecks("day=3", async () => new Response("", { status: 400 }));

    expect(asked).toEqual(["/api/plants/checks?day=3&seed=1&environment=reference"]);
    expect(loaded).toEqual({ status: "loaded", day: 3, problems: { p01: [] } });
    expect(refused).toEqual({ status: "unavailable", reason: "the simulator API answered 400" });
  });
});
