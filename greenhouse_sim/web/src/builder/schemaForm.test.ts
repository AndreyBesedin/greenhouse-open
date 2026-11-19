import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { ASSESSED_SCHEMA } from "./generated/assessedSchema";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import {
  formFields,
  formValues,
  modelFields,
  parameterFields,
  rangeText,
  startingValues,
} from "./schemaForm";

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
      choices: ["simple", "organ", "reduced_tomgro", "vanthoor_katzin"],
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

/** A crop model's parameters' schema, as the simulator publishes it and serves
 * it to a parameter set's form (P20.1). */
function parametersSchema(model: "tomgro" | "vanthoor"): Record<string, unknown> {
  const published = new URL(
    `../../../greenhouse_sim/biology/tomato/${model}/parameters.schema.json`,
    import.meta.url,
  );
  return JSON.parse(readFileSync(published, "utf8"));
}

describe("a crop model's parameters read from the schema the simulator publishes (P20.5)", () => {
  it("has each parameter, in its order, with what it is, its unit, source and range", () => {
    const fields = parameterFields(parametersSchema("tomgro"));
    const byName = new Map(fields.map((field) => [field.name, field]));

    expect(fields.map((field) => field.name).slice(0, 3)).toEqual(["alpha_f", "beta", "delta"]);
    expect(byName.get("alpha_f")).toEqual({
      name: "alpha_f",
      what: "alpha_F: the share of the day's net growth to the fruit, at most",
      unit: "fraction d⁻¹",
      source: expect.stringContaining("Oliveira et al. v0.4.0"),
      least: { value: 0, exclusive: false },
      most: { value: 1, exclusive: false },
      leastFrom: "none in its source: the field's type's",
      mostFrom: expect.stringContaining("a share, of all of it at most"),
      fixed: null,
    });
    // An end a value must stay inside of, and a field bounded at neither end.
    expect(byName.get("m")).toMatchObject({ most: { value: 1, exclusive: true } });
    expect(byName.get("beta")).toMatchObject({ least: null, most: null });
  });

  it("says which parameters no set changes, and why", () => {
    const fixed = (model: "tomgro" | "vanthoor") =>
      parameterFields(parametersSchema(model))
        .filter((field) => field.fixed !== null)
        .map((field) => [field.name, field.fixed]);

    expect(fixed("tomgro")).toEqual([
      ["d", "a conversion of units: no set changes it"],
      ["trgh", expect.stringContaining("as the run gives the PPFD inside the greenhouse")],
    ]);
    expect(fixed("vanthoor").map(([name]) => name)).toEqual(["m_ch2o", "t25k", "r"]);
  });

  it("reads a schema that says little as far as it says", () => {
    expect(parameterFields({ properties: { x: { title: "X" }, y: 3 } })).toEqual([
      {
        name: "x",
        what: "X",
        unit: "",
        source: "",
        least: null,
        most: null,
        leastFrom: "",
        mostFrom: "",
        fixed: null,
      },
      expect.objectContaining({ name: "y", what: "y" }),
    ]);
    expect(parameterFields({})).toEqual([]);
  });

  it("says a range in words, each end as at most or below, at least or above", () => {
    const at = (value: number) => ({ value, exclusive: false });
    const beyond = (value: number) => ({ value, exclusive: true });

    expect(rangeText({ least: at(0), most: at(1) })).toBe("from 0 to 1");
    expect(rangeText({ least: at(0), most: beyond(1) })).toBe("at least 0 and below 1");
    expect(rangeText({ least: beyond(0), most: at(1) })).toBe("above 0 and at most 1");
    expect(rangeText({ least: beyond(0), most: null })).toBe("above 0");
    expect(rangeText({ least: null, most: at(1) })).toBe("at most 1");
    expect(rangeText({ least: null, most: null })).toBe("any number");
  });
});
