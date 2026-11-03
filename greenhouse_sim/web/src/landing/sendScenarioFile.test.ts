import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { uploadScenarioFile } from "./sendScenarioFile";

// The fields the page reads of what the simulator answers an upload of the Climate box's file under another
// identifier.
const UPLOADED = JSON.parse(
  readFileSync(join(process.cwd(), "src/landing/testing/uploadedScenario.json"), "utf8"),
);

function file(text: string, size = text.length) {
  return { name: "shared.scenario.json", size, text: async () => text };
}

describe("a scenario file sent to the simulator (P17.11)", () => {
  it("is read for what the simulator registered of it", async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify(UPLOADED)));

    const answer = await uploadScenarioFile(file("{}"), fetchFn as unknown as typeof fetch);

    expect(answer.ok && answer.value.scenario?.id).toBe("shared_box");
    expect(answer.ok && answer.value.settings.duration_days).toBeGreaterThan(0);
    expect(fetchFn).toHaveBeenCalledWith(
      "/api/scenarios/upload",
      expect.objectContaining({ method: "POST", body: "{}" }),
    );
  });

  it("is not sent when it is more than the simulator reads", async () => {
    const fetchFn = vi.fn();

    const answer = await uploadScenarioFile(file("{}", 9_500_000), fetchFn);

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

    const answer = await uploadScenarioFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: false,
      problem: `shared.scenario.json cannot be opened: ${error}`,
    });
  });

  it("is refused when the simulator's answer is not an upload's", async () => {
    const fetchFn = async () => new Response(JSON.stringify({ kept: true }));

    const answer = await uploadScenarioFile(file("{}"), fetchFn);

    expect(answer).toEqual({
      ok: false,
      problem: "shared.scenario.json cannot be opened: not an uploaded scenario",
    });
  });
});
