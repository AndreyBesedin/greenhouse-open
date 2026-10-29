import { describe, expect, it } from "vitest";

import { ASSESSED_SCHEMA } from "./generated/assessedSchema";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import { formFields, formValues, modelFields, startingValues } from "./schemaForm";

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
      maximum: 100,
    });
    expect(fields.find((field) => field.name === "crop_model")).toMatchObject({
      kind: "choice",
      choices: ["simple", "organ", "reduced_tomgro"],
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

describe("a model's fields read from the schema the simulator publishes (P12.3)", () => {
  const schema: Record<string, unknown> = ASSESSED_SCHEMA;

  it("has each field of a model, a nested object's by its path and titled by what holds it", () => {
    const fields = modelFields(schema, "Heater");

    expect(fields.map((field) => [field.path, field.title, field.kind])).toEqual([
      ["actuator_id", "Actuator Id", "text"],
      ["heading", "Heading", "number"],
      ["base.x", "Base X", "number"],
      ["base.y", "Base Y", "number"],
      ["base.z", "Base Z", "number"],
      ["size_x", "Size X", "number"],
      ["size_y", "Size Y", "number"],
      ["size_z", "Size Z", "number"],
      ["power_w", "Power W", "number"],
    ]);
  });

  it("leaves out lists, a constant kind, and a rotation no one types by hand", () => {
    const paths = modelFields(schema, "Envelope", "envelope.").map((field) => field.path);

    // Its openings are a list; its turn in the world, a quaternion.
    expect(paths).toEqual([
      "envelope.length",
      "envelope.width",
      "envelope.eave_height",
      "envelope.ridge_height",
      "envelope.spans",
      "envelope.bays",
      "envelope.origin.position.x",
      "envelope.origin.position.y",
      "envelope.origin.position.z",
    ]);
  });

  it("follows a model two objects deep: the ends of a zone's area", () => {
    const fields = modelFields(schema, "Zone");

    expect(fields.map((field) => [field.path, field.title])).toEqual([
      ["zone_id", "Zone Id"],
      ["kind", "Kind"],
      ["area.start.x", "Area Start X"],
      ["area.start.y", "Area Start Y"],
      ["area.end.x", "Area End X"],
      ["area.end.y", "Area End Y"],
      ["area.width", "Area Width"],
      ["height", "Height"],
    ]);
  });

  it("follows a model a field may hold or not, and says which fields may be null", () => {
    const rows = modelFields(schema, "CropRows", "layout.crop_rows.");
    const byPath = new Map(rows.map((field) => [field.path, field]));

    // A row's gutter, `RowSupport | None`: its fields, not one of text.
    expect(byPath.has("layout.crop_rows.support")).toBe(false);
    expect(byPath.get("layout.crop_rows.support.height")).toMatchObject({
      title: "Support Height",
      kind: "number",
    });
    expect(byPath.get("layout.crop_rows.pair_gap")).toMatchObject({ nullable: true });
    expect(byPath.get("layout.crop_rows.rows")).toMatchObject({ nullable: false });
  });

  it("offers a choice's values, and takes a flag as true or false", () => {
    const opening = modelFields(schema, "Opening");

    expect(opening.find((field) => field.path === "kind")).toMatchObject({
      kind: "choice",
      choices: ["door", "roof_vent", "side_vent"],
    });
    expect(modelFields(schema, "Imperfections").map((field) => field.kind)).not.toContain("choice");
  });
});
