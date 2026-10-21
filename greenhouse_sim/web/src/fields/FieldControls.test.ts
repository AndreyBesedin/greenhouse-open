import { describe, expect, it } from "vitest";

import { describeAirField, loadFieldNames } from "./FieldControls";

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

describe("the air field's section, folded", () => {
  it("says which field is drawn, how, and whether CFD's boundaries are over it (#273)", () => {
    expect(describeAirField(null, "arrows", false)).toBe("Air field: none");
    expect(describeAirField("climate", "slice", false)).toBe("Air field: climate, as slice");
    expect(describeAirField("cfd", "streamlines", true)).toBe(
      "Air field: cfd, as streamlines; CFD boundaries drawn",
    );
  });
});
