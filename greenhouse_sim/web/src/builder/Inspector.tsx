import { type KeyboardEvent, useId } from "react";

import { isObject } from "../loadJson";
import { ASSESSED_SCHEMA } from "./generated/assessedSchema";
import type { Installation } from "./generated/assessedTypes";
import type { Edit } from "./generated/editTypes";
import { type ModelField, modelFields } from "./schemaForm";

/** An item of the installation the inspector shows: its identifier, the
 * schema's model of it, and its fields' values. */
interface Inspected {
  id: string;
  model: string;
  values: unknown;
}

const EQUIPMENT_MODELS: Readonly<Record<string, string>> = {
  fan: "Fan",
  heater: "Heater",
  dehumidifier: "Dehumidifier",
};

const FIXTURE_MODELS: Readonly<Record<string, string>> = {
  box: "BoxPrimitive",
  cylinder: "CylinderPrimitive",
  pipe: "PipePrimitive",
  pipe_run: "PipeRunPrimitive",
  rail: "RailPrimitive",
  tray: "TrayPrimitive",
  walkway: "WalkwayPrimitive",
};

/** The equipment, sensor, zone, fixture, door or vent named `id`, with its
 * model. */
function inspected(installation: Installation, id: string): Inspected | null {
  const piece = installation.layout.equipment?.find((each) => each.actuator_id === id);
  if (piece !== undefined) {
    return { id, model: EQUIPMENT_MODELS[piece.kind ?? ""] ?? "Fan", values: piece };
  }
  const sensor = installation.layout.sensors?.find((each) => each.sensor_id === id);
  if (sensor !== undefined) {
    return { id, model: sensor.kind === "camera" ? "Camera" : "PointSensor", values: sensor };
  }
  const zone = installation.layout.zones?.find((each) => each.zone_id === id);
  if (zone !== undefined) {
    return { id, model: "Zone", values: zone };
  }
  const fixture = installation.layout.placed?.find((each) => each.fixture_id === id);
  const model = FIXTURE_MODELS[fixture?.primitive ?? ""];
  if (fixture !== undefined && model !== undefined) {
    return { id, model, values: fixture };
  }
  const opening = installation.envelope.openings?.find((each) => each.opening_id === id);
  return opening === undefined ? null : { id, model: "Opening", values: opening };
}

// How many significant digits a number is shown to: more than any size a
// greenhouse is measured to, fewer than a float's rounding shows, as in
// (6.4 - 1.6) / 2, 2.4000000000000004.
const SHOWN_DIGITS = 12;

/** What `values` holds at `path`, as an input shows it: a number to
 * `SHOWN_DIGITS`, so that a value left as it is sends nothing, and the
 * simulator keeps it exact. */
function shown(values: unknown, path: string): string {
  let held: unknown = values;
  for (const key of path.split(".")) {
    held = isObject(held) ? held[key] : undefined;
  }
  if (typeof held === "number") {
    return String(Number(held.toPrecision(SHOWN_DIGITS)));
  }
  return held === undefined || held === null ? "" : String(held);
}

/** What a field is given: a number, a flag, a text, or none at all. */
type Given = number | boolean | string | null;

/** A value as the field takes it: a number's as a number, where it reads as
 * one, for the simulator to check; a flag's as true or false; and nothing,
 * null, for a field that may have none, emptied. */
function typed(field: ModelField, text: string): Given {
  if (field.kind === "flag") {
    return text === "true";
  }
  if (field.nullable && text.trim() === "") {
    return null;
  }
  const asNumber = Number(text);
  return (field.kind === "number" || field.kind === "integer") &&
    text.trim() !== "" &&
    Number.isFinite(asNumber)
    ? asNumber
    : text;
}

function Field({
  field,
  value,
  busy,
  onCommit,
}: {
  field: ModelField;
  value: string;
  busy: boolean;
  onCommit: (field: ModelField, value: Given) => void;
}) {
  function commit(text: string): void {
    if (text !== value) {
      onCommit(field, typed(field, text));
    }
  }
  // Enter leaves the field, which sends its value: once, as leaving it
  // any other way does.
  function onKey(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter") {
      event.currentTarget.blur();
    }
  }
  if (field.kind === "flag") {
    return (
      <label className="builder-give-field">
        <input
          type="checkbox"
          disabled={busy}
          checked={value === "true"}
          onChange={(event) => onCommit(field, event.target.checked)}
        />
        <span>{field.title}</span>
      </label>
    );
  }
  if (field.kind === "choice") {
    return (
      <label className="builder-give-field">
        <span>{field.title}</span>
        <select disabled={busy} value={value} onChange={(event) => commit(event.target.value)}>
          {field.choices.map((choice) => (
            <option key={choice} value={choice}>
              {choice.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
    );
  }
  // Typed into freely, and sent once left or entered: the field's own value
  // again when the installation changes.
  return (
    <label className="builder-give-field">
      <span>{field.title}</span>
      <input
        key={value}
        type={field.kind === "text" ? "text" : "number"}
        step="any"
        disabled={busy}
        defaultValue={value}
        min={field.minimum}
        max={field.maximum}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={onKey}
      />
    </label>
  );
}

/**
 * Every field of the item chosen, or of the house when none is (P12.3):
 * read from the schema the simulator publishes, so that no field is written
 * twice. A value changed is one edit the simulator makes and checks, a
 * field of an item by `set_field`, one of the house by `set_value`, and is
 * undone in one step.
 */
export function Inspector({
  installation,
  chosen,
  busy,
  onEdit,
}: {
  installation: Installation;
  /** The one item chosen, if one is. */
  chosen: string | null;
  busy: boolean;
  onEdit: (edit: Edit, said: string) => void;
}) {
  const heading = useId();
  const item = chosen === null ? null : inspected(installation, chosen);
  const schema = ASSESSED_SCHEMA as Record<string, unknown>;

  if (item !== null) {
    return (
      <section className="builder-inspector" aria-labelledby={heading}>
        <h2 id={heading}>{item.id}</h2>
        <div className="builder-give">
          {modelFields(schema, item.model).map((field) => (
            <Field
              key={field.path}
              field={field}
              value={shown(item.values, field.path)}
              busy={busy}
              onCommit={(changed, value) =>
                onEdit(
                  { edit: "set_field", items: [item.id], path: changed.path, value },
                  `Set ${changed.title.toLowerCase()} of ${item.id}.`,
                )
              }
            />
          ))}
        </div>
      </section>
    );
  }
  const house = [
    ...modelFields(schema, "Envelope", "envelope."),
    ...(installation.layout.crop_rows ? modelFields(schema, "CropRows", "layout.crop_rows.") : []),
  ];
  return (
    <section className="builder-inspector" aria-labelledby={heading}>
      <h2 id={heading}>Envelope and rows</h2>
      <div className="builder-give">
        {house.map((field) => (
          <Field
            key={field.path}
            field={field}
            value={shown(installation, field.path)}
            busy={busy}
            onCommit={(changed, value) =>
              onEdit(
                { edit: "set_value", path: changed.path, value },
                `Set ${changed.title.toLowerCase()} of the house.`,
              )
            }
          />
        ))}
      </div>
    </section>
  );
}
