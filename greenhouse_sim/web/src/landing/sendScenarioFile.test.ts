import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { uploadFile } from "./sendScenarioFile";

// The fields the page reads of what the simulator answers an upload of the Climate box's file under another
// identifier.
const UPLOADED = JSON.parse(
  readFileSync(join(process.cwd(), "src/landing/testing/uploadedScenario.json"), "utf8"),
);

const STARTING_HOUSE = JSON.parse(
  readFileSync(join(process.cwd(), "src/builder/testing/startingHouse.json"), "utf8"),
);

function file(text: string, size = text.length) {
  return { name: "shared.scenario.json", size, text: async () => text };
}

describe("a scenario file sent to the simulator (P17.11)", () => {
  it("is read for what the simulator registered of it", async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify(UPLOADED)));

    const answer = await uploadFile(file("{}"), fetchFn as unknown as typeof fetch);

    if (!answer.ok || answer.value.kind !== "scenario") {
      throw new Error("not a scenario's answer");
    }
    expect(answer.value.scenario?.id).toBe("shared_box");
    expect(answer.value.settings.duration_days).toBeGreaterThan(0);
    expect(fetchFn).toHaveBeenCalledWith(
      "/api/scenarios/upload",
      expect.objectContaining({ method: "POST", body: "{}" }),
    );
  });

  it("is read as an installation's when the simulator says it is one", async () => {
    const fetchFn = async () =>
      new Response(JSON.stringify({ kind: "installation", assessed: STARTING_HOUSE }));

    const answer = await uploadFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: true,
      value: { kind: "installation", assessed: STARTING_HOUSE },
    });
  });

  it("is refused when an installation's answer is not an assessed house", async () => {
    const fetchFn = async () =>
      new Response(JSON.stringify({ kind: "installation", assessed: { installation: {} } }));

    const answer = await uploadFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: false,
      problem: "shared.scenario.json cannot be opened: not an assessed installation",
    });
  });

  it("is not sent when it is more than the simulator reads", async () => {
    const fetchFn = vi.fn();

    const answer = await uploadFile(file("{}", 9_500_000), fetchFn);

    expect(fetchFn).not.toHaveBeenCalled();
    expect(answer).toEqual({
      ok: false,
      problem: "shared.scenario.json is 9.5 MB, more than the 8 MB the simulator reads",
    });
  });

  it.each([
    [400, "not a scenario file: schema_version 99 is not read"],
    [409, "'climate_box' is a packaged scenario's identifier"],
  ])("is refused with the simulator's words, as %s", async (status, error) => {
    const fetchFn = async () => new Response(JSON.stringify({ error }), { status });

    const answer = await uploadFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: false,
      problem: `shared.scenario.json cannot be opened: ${error}`,
    });
  });

  it("is refused when the simulator's answer is not an upload's", async () => {
    const fetchFn = async () => new Response(JSON.stringify({ kept: true }));

    const answer = await uploadFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: false,
      problem: "shared.scenario.json cannot be opened: not an uploaded scenario",
    });
  });
});
