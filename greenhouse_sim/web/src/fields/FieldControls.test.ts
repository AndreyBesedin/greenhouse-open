import { describe, expect, it } from "vitest";

import { loadFieldNames } from "./FieldControls";

describe("a scenario's fields", () => {
  it("are listed with its own airflow, and none if they cannot be read", async () => {
    const listed = await loadFieldNames(
      "gh_001",
      async () =>
        new Response(JSON.stringify({ fields: ["vortex", "uniform"], configured: "vortex" }), {
          status: 200,
        }),
    );
    const missing = await loadFieldNames("gh_999", async () => new Response("", { status: 404 }));

    expect(listed).toEqual({ names: ["vortex", "uniform"], configured: "vortex" });
    expect(missing).toEqual({ names: [], configured: null });
  });
});
