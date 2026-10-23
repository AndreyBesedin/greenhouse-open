import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { edit, firstDraft, installationFile, openDraft, refusal, saveDraft } from "./api";
import type { Installation } from "./generated/assessedTypes";
import type { Edit } from "./generated/editTypes";

function answering(status: number, body: unknown, asked: Request[] = []): typeof fetch {
  return async (input, init) => {
    asked.push(new Request(new URL(String(input), "http://localhost"), init));
    return new Response(JSON.stringify(body), { status });
  };
}

const HOUSE = { installation_id: "house", name: "House" } as unknown as Installation;
// The builder's answer about an installation, as the simulator sends it.
const ASSESSED = JSON.parse(
  readFileSync(join(process.cwd(), "src/builder/testing/startingHouse.json"), "utf8"),
);
const KEPT = { draft_id: "house", revision: 2, saved_at: "2026-10-23T12:00:00Z" };

describe("the builder's side of the API (P12.2)", () => {
  it("writes an installation's file as an import reads it", () => {
    expect(JSON.parse(installationFile(4, HOUSE))).toEqual({
      schema_version: 4,
      installation_id: "house",
      name: "House",
    });
  });

  it("saves on the revision it was made on, or as a new draft", async () => {
    const asked: Request[] = [];
    await saveDraft("my house", "{}", 3, answering(409, { error: "stale" }, asked));
    await saveDraft("house", "{}", null, answering(409, { error: "kept" }, asked));

    expect(
      asked.map((request) => [
        request.method,
        new URL(request.url).pathname + new URL(request.url).search,
      ]),
    ).toEqual([
      ["POST", "/api/drafts/my%20house/save?on=3"],
      ["POST", "/api/drafts/house/save"],
    ]);
  });

  it("says why the simulator refused, in its words, or by its status", async () => {
    expect(
      await firstDraft({} as never, answering(400, { error: "rows: Field required" })),
    ).toEqual({
      ok: false,
      problem: "rows: Field required",
    });
    expect(await refusal(new Response("not JSON", { status: 502 }))).toBe(
      "the simulator API answered 502",
    );
  });

  it("sends an edit with the installation's file it is made on", async () => {
    const asked: Request[] = [];
    const change: Edit = { edit: "remove_items", items: ["heater_1"] };

    const answer = await edit(4, HOUSE, change, answering(400, { error: "no item" }, asked));

    expect(answer).toEqual({ ok: false, problem: "no item" });
    const [sent] = asked;
    expect(new URL(sent?.url ?? "").pathname).toBe("/api/builder/edit");
    expect(await sent?.json()).toEqual({
      file: { schema_version: 4, installation_id: "house", name: "House" },
      edit: change,
    });
  });

  it("refuses an answer that is not what its contract says", async () => {
    const opened = await openDraft("house", 2, answering(200, { draft_id: "house" }));

    expect(opened).toEqual({ status: "unavailable", reason: "not a draft" });
  });

  it("opens a draft as the builder's answer about its installation, naming it", async () => {
    const opened = await openDraft("house", 2, answering(200, { ...ASSESSED, draft: KEPT }));

    expect(opened).toEqual({ status: "loaded", value: { ...ASSESSED, draft: KEPT } });
  });

  it("refuses, as a draft, an answer about an installation that names none", async () => {
    const opened = await openDraft("house", 2, answering(200, ASSESSED));

    expect(opened).toEqual({ status: "unavailable", reason: "not a draft" });
  });
});
