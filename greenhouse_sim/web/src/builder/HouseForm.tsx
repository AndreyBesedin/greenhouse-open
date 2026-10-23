import { type FormEvent, useId, useMemo, useState } from "react";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import type { BasicSetup } from "./generated/basicTypes";
import { formFields, formValues, startingValues } from "./schemaForm";

const SCHEMA: Record<string, unknown> = BASIC_SETUP_SCHEMA;

/**
 * The builder's first form (P12.2): a house of equal spans and bays and its
 * rows of one crop, its fields as the simulator publishes them
 * (`builder/basic.schema.json`), starting from its example house.
 */
export function HouseForm({
  busy,
  onDraft,
}: {
  busy: boolean;
  onDraft: (values: BasicSetup) => void;
}) {
  const fields = useMemo(() => formFields(SCHEMA), []);
  const [entered, setEntered] = useState(() => startingValues(SCHEMA));
  const heading = useId();

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    // The simulator checks the values, and says by field what it refuses.
    onDraft(formValues(fields, entered) as unknown as BasicSetup);
  }

  return (
    <form className="builder-form" aria-labelledby={heading} onSubmit={submit}>
      <h2 id={heading}>A new house</h2>
      {fields.map((field) => (
        <div key={field.name} className="builder-field">
          <label htmlFor={`${heading}-${field.name}`}>{field.title}</label>
          {field.kind === "choice" ? (
            <select
              id={`${heading}-${field.name}`}
              name={field.name}
              value={entered[field.name] ?? ""}
              onChange={(event) => setEntered({ ...entered, [field.name]: event.target.value })}
            >
              {field.choices.map((choice) => (
                <option key={choice} value={choice}>
                  {choice}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`${heading}-${field.name}`}
              name={field.name}
              type={field.kind === "text" ? "text" : "number"}
              step={field.kind === "integer" ? 1 : "any"}
              required={field.required}
              value={entered[field.name] ?? ""}
              onChange={(event) => setEntered({ ...entered, [field.name]: event.target.value })}
            />
          )}
        </div>
      ))}
      <button type="submit" disabled={busy}>
        Draft this house
      </button>
    </form>
  );
}
