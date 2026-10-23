import { describe, expect, it } from "vitest";

import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import { formFields, formValues, startingValues } from "./schemaForm";

const SCHEMA: Record<string, unknown> = BASIC_SETUP_SCHEMA;

describe("a form read from the schema the simulator publishes (P12.2)", () => {
  it("has a field for each property, labelled by its title, entered as its type says", () => {
    const fields = formFields(SCHEMA);

    expect(fields.map((field) => field.name)).toEqual(Object.keys(BASIC_SETUP_SCHEMA.properties));
    expect(fields.find((field) => field.name === "length_m")).toMatchObject({
      title: "Length (m)",
      kind: "number",
      required: true,
    });
    expect(fields.find((field) => field.name === "spans")).toMatchObject({
      kind: "integer",
      required: false,
    });
    expect(fields.find((field) => field.name === "crop_model")).toMatchObject({
      kind: "choice",
      choices: ["simple", "organ"],
    });
    expect(fields.find((field) => field.name === "name")?.kind).toBe("text");
  });

  it("starts from the schema's example house", () => {
    const values = startingValues(SCHEMA);

    expect(values.name).toBe("My greenhouse");
    expect(values.length_m).toBe("12");
    expect(values.crop_model).toBe("simple");
  });

  it("sends numbers as numbers, leaves out what is empty, and the rest as written", () => {
    const fields = formFields(SCHEMA);

    expect(
      formValues(fields, { length_m: " 12.5 ", rows: "2", name: "House", width_m: "", bays: "x" }),
    ).toEqual({
      length_m: 12.5,
      rows: 2,
      name: "House",
      bays: "x",
    });
  });
});
