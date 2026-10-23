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

/** A field of one of the schema's models, as an inspector shows it: its
 * path within the model, a nested object's by its own (`base.x`). A flag is
 * a field that is true or false. */
export interface ModelField extends Omit<FormField, "kind" | "name" | "required"> {
  path: string;
  kind: FieldKind | "flag";
}

// How deep the inspector follows a model's nested objects: a position's
// coordinates, a sensor's imperfections, not a transform's rotation.
const DEEPEST = 1;

/** The one kind of value a property holds, if it allows null besides. */
function oneOf(property: Record<string, unknown>): Record<string, unknown> | null {
  if (!Array.isArray(property.anyOf)) {
    return property;
  }
  const kinds = property.anyOf.filter((each) => isObject(each) && each.type !== "null");
  const [only] = kinds;
  return kinds.length === 1 && isObject(only) ? { ...property, ...only } : null;
}

function capitalised(key: string): string {
  const words = key.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The fields of the schema's model `name`, in their order, a nested
 * object's by their path; a list, and a field that holds values of more
 * than one kind, are left out, for an edit of their own. */
export function modelFields(
  schema: Record<string, unknown>,
  name: string,
  prefix = "",
  depth = 0,
  within = "",
): ModelField[] {
  const definitions = isObject(schema.$defs) ? schema.$defs : {};
  const model = definitions[name];
  const properties = isObject(model) && isObject(model.properties) ? model.properties : {};
  return Object.entries(properties).flatMap(([key, property]): ModelField[] => {
    const field = oneOf(resolved(schema, property));
    // A list has edits of its own; a constant, such as a kind, is no field
    // to change.
    if (field === null || field.type === "array" || "const" in field) {
      return [];
    }
    const path = `${prefix}${key}`;
    const reference = isObject(property) && typeof property.$ref === "string" ? property.$ref : "";
    // A field is titled by its own title, never its model's ("Vector3",
    // "OpeningKind"), or else by its name.
    const own = isObject(property) ? property.title : undefined;
    const title =
      typeof own === "string"
        ? own
        : reference === "" && typeof field.title === "string"
          ? field.title
          : capitalised(key);
    if (isObject(field.properties)) {
      // A nested field is titled by what holds it too: "Base X".
      return depth < DEEPEST
        ? modelFields(
            schema,
            reference.replace("#/$defs/", ""),
            `${path}.`,
            depth + 1,
            `${within}${title} `,
          )
        : [];
    }
    const choices = Array.isArray(field.enum) ? field.enum.map(String) : [];
    const kind: ModelField["kind"] =
      choices.length > 0
        ? "choice"
        : field.type === "boolean"
          ? "flag"
          : field.type === "integer"
            ? "integer"
            : field.type === "number"
              ? "number"
              : "text";
    return [
      {
        path,
        title: `${within}${title}`,
        kind,
        choices,
        ...(typeof field.minimum === "number" ? { minimum: field.minimum } : {}),
        ...(typeof field.maximum === "number" ? { maximum: field.maximum } : {}),
      },
    ];
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
