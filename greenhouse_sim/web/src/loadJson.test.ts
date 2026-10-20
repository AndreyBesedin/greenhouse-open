import { describe, expect, it } from "vitest";

import { contractCheck, contractReader, isNumberRecord, isObject, loadJson } from "./loadJson";

function answering(status: number, body: string): typeof fetch {
  return async () => new Response(body, { status });
}

const parseCount = (body: unknown): number => {
  if (!isObject(body) || typeof body.count !== "number") {
    throw new Error("no count");
  }
  return body.count;
};

describe("a document fetched from the simulator", () => {
  it("is read by its parser", async () => {
    expect(await loadJson("/x", parseCount, answering(200, '{"count": 3}'))).toEqual({
      status: "loaded",
      value: 3,
    });
  });

  it("is unavailable, saying why, when the answer is refused, not JSON, or not read", async () => {
    expect(await loadJson("/x", parseCount, answering(500, "{}"))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 500",
    });
    const own = async (response: Response) => `refused: ${response.status}`;
    expect(await loadJson("/x", parseCount, answering(404, "{}"), own)).toEqual({
      status: "unavailable",
      reason: "refused: 404",
    });
    expect((await loadJson("/x", parseCount, answering(200, "<html>"))).status).toBe("unavailable");
    expect(await loadJson("/x", parseCount, answering(200, '{"count": "3"}'))).toEqual({
      status: "unavailable",
      reason: "no count",
    });
    const unreachable: typeof fetch = async () => {
      throw new TypeError("Failed to fetch");
    };
    expect(await loadJson("/x", parseCount, unreachable)).toEqual({
      status: "unavailable",
      reason: "Failed to fetch",
    });
  });
});

// A contract as the simulator publishes one: a count, and the instant it was
// taken at, whose format is read as the text it is.
const COUNTED = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  type: "object",
  properties: {
    count: { type: "integer" },
    at: { type: "string", format: "date-time" },
  },
  required: ["count", "at"],
};

describe("a body checked against its contract", () => {
  const check = contractCheck<{ count: number; at: string }>(COUNTED, "the count");

  it("is the body, when the contract describes it", () => {
    expect(check({ count: 3, at: "noon" })).toEqual({ ok: true, value: { count: 3, at: "noon" } });
  });

  it("is what is wrong with it, where, otherwise", () => {
    expect(check({ count: 2.5 })).toEqual({
      ok: false,
      problems: ["the count must have required property 'at'", "/count must be integer"],
    });
    expect(check([])).toEqual({ ok: false, problems: ["the count must be object"] });
  });

  it("is refused in the loader's own words by a reader", () => {
    const read = contractReader<{ count: number }>(
      COUNTED,
      "the count is not what the viewer expects",
    );

    expect(read({ count: 3, at: "noon" })).toEqual({ count: 3, at: "noon" });
    expect(() => read({ count: "3" })).toThrow("the count is not what the viewer expects");
  });
});

describe("the wire's checks by hand, for what has no contract", () => {
  it("tell numbers by name from a list", () => {
    expect(isNumberRecord({ a: 1, b: 2 })).toBe(true);
    expect(isNumberRecord({ a: "1" })).toBe(false);
    expect(isNumberRecord([1, 2])).toBe(false);
    expect(isNumberRecord(null)).toBe(false);
  });
});
