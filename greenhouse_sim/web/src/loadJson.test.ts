import { describe, expect, it } from "vitest";

import { isNumberList, isNumberRecord, isObject, loadJson } from "./loadJson";

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

describe("the wire's shared checks", () => {
  it("tell numbers in a list from numbers by name", () => {
    expect(isNumberList([1, 2.5])).toBe(true);
    expect(isNumberList([1, 2], 3)).toBe(false);
    expect(isNumberList([1, "2"])).toBe(false);
    expect(isNumberList({ a: 1 })).toBe(false);
    expect(isNumberRecord({ a: 1, b: 2 })).toBe(true);
    expect(isNumberRecord({ a: "1" })).toBe(false);
    expect(isNumberRecord([1, 2])).toBe(false);
    expect(isNumberRecord(null)).toBe(false);
  });
});
