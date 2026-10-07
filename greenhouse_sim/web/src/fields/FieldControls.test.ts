import { describe, expect, it } from "vitest";

import { loadFieldNames } from "./FieldControls";

describe("a scenario's fields", () => {
  it("are listed with its own airflow and layout, and none if they cannot be read", async () => {
    const asked: string[] = [];
    const listed = await loadFieldNames("airflow_box", "open", async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify({ fields: ["uniform", "cfd"], configured: "uniform" }), {
        status: 200,
      });
    });
    const missing = await loadFieldNames(
      "gh_999",
      undefined,
      async () => new Response("", { status: 404 }),
    );

    expect(asked).toEqual(["/api/scenarios/airflow_box/fields?layout=open"]);
    expect(listed).toEqual({ names: ["uniform", "cfd"], configured: "uniform" });
    expect(missing).toEqual({ names: [], configured: null });
  });
});
