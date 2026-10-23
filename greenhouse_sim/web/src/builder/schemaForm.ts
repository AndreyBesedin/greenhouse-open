/**
 * A form read from the JSON Schema the simulator publishes for its values
 * (P12, "one schema"): each field's label is its title, its input follows
 * its type, a choice offers its enumeration's values, and the form starts
 * from the schema's first example. No field is written twice, here and in
 * the simulator.
 */

import { isObject } from "../loadJson";

/** How a field is entered. */
export type FieldKind = "number" | "integer" | "text" | "choice";

export interface FormField {
  name: string;
  title: string;
  kind: FieldKind;
  /** A choice's values, in the schema's order. */
  choices: string[];
  required: boolean;
  /** A number's bounds, where the schema gives them, as an input takes
   * them; an exclusive minimum is left to the simulator to say. */
  minimum?: number;
  maximum?: number;
}

function resolved(schema: Record<string, unknown>, property: unknown): Record<string, unknown> {
  if (!isObject(property)) {
    return {};
  }
  const reference = property.$ref;
  if (typeof reference !== "string") {
    return property;
  }
  const name = reference.replace("#/$defs/", "");
  const definitions = isObject(schema.$defs) ? schema.$defs : {};
  const found = definitions[name];
  return isObject(found) ? { ...found, ...property } : property;
}

/** The fields a schema's properties describe, in their order. */
export function formFields(schema: Record<string, unknown>): FormField[] {
  const properties = isObject(schema.properties) ? schema.properties : {};
  const required = new Set(Array.isArray(schema.required) ? schema.required : []);
  return Object.entries(properties).map(([name, property]) => {
    const field = resolved(schema, property);
    const choices = Array.isArray(field.enum) ? field.enum.map(String) : [];
    const kind: FieldKind =
      choices.length > 0
        ? "choice"
        : field.type === "integer"
          ? "integer"
          : field.type === "number"
            ? "number"
            : "text";
    const title = typeof field.title === "string" ? field.title : name;
    return {
      name,
      title,
      kind,
      choices,
      required: required.has(name),
      ...(typeof field.minimum === "number" ? { minimum: field.minimum } : {}),
      ...(typeof field.maximum === "number" ? { maximum: field.maximum } : {}),
    };
  });
}

/** What the form shows at first: the schema's first example, each value as
 * an input holds it, and nothing for a field it does not give. */
export function startingValues(schema: Record<string, unknown>): Record<string, string> {
  const [example] = Array.isArray(schema.examples) ? schema.examples : [];
  const given = isObject(example) ? example : {};
  return Object.fromEntries(
    formFields(schema).map((field) => [
      field.name,
      given[field.name] === undefined ? "" : String(given[field.name]),
    ]),
  );
}

/** The values the form sends: a number's as a number where it reads as
 * one, and as written otherwise, so that the simulator says what is wrong
 * with it; a field left empty is left out. */
export function formValues(
  fields: readonly FormField[],
  entered: Readonly<Record<string, string>>,
): Record<string, string | number> {
  const values: Record<string, string | number> = {};
  for (const field of fields) {
    const text = (entered[field.name] ?? "").trim();
    if (text === "") {
      continue;
    }
    const number = Number(text);
    values[field.name] =
      (field.kind === "number" || field.kind === "integer") && Number.isFinite(number)
        ? number
        : text;
  }
  return values;
}
