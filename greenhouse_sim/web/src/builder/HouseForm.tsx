import { type FormEvent, useId, useMemo, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import { Notice } from "../design/Notice";
import type { FieldProblem } from "./api";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import type { BasicSetup } from "./generated/basicTypes";
import { formFields, formValues, startingValues } from "./schemaForm";
import { describedBy, keptAlready, WhyNot } from "./WhyNot";

const SCHEMA: Record<string, unknown> = BASIC_SETUP_SCHEMA;

/** The field that names the house, as its drafts are named. */
const IDENTIFIER_FIELD = "installation_id";

/**
 * The builder's first form (P12.2): a house of equal spans and bays and its
 * rows of one crop, its fields as the simulator publishes them
 * (`builder/basic.schema.json`), starting from its example house.
 *
 * What stops it is said where it is: an identifier a kept draft has at its
 * field, before the house is drafted, since that draft could never be saved
 * under it; and what the simulator refused of the values sent, at each
 * field it names, until that field is changed, with its whole answer below
 * the button.
 */
export function HouseForm({
  busy,
  kept = [],
  problems = [],
  refused,
  onDraft,
}: {
  busy: boolean;
  /** The identifiers of the drafts kept. */
  kept?: readonly string[];
  /** Each field the simulator refused of the values last sent. */
  problems?: readonly FieldProblem[];
  /** Why the simulator refused the values last sent, if it did. */
  refused?: string | undefined;
  onDraft: (values: BasicSetup) => void;
}) {
  const fields = useMemo(() => formFields(SCHEMA), []);
  const [entered, setEntered] = useState(() => startingValues(SCHEMA));
  // The values last sent, which the simulator's problems are about.
  const [sent, setSent] = useState<Record<string, string> | null>(null);
  const heading = useId();
  const why = useId();
  const draftId = (entered[IDENTIFIER_FIELD] ?? "").trim();
  const taken = kept.includes(draftId) ? [keptAlready(draftId)] : [];

  /** What is wrong with a field: an identifier taken, or what the simulator
   * refused of it, while it holds what was sent. */
  function problemOf(name: string): string | undefined {
    if (name === IDENTIFIER_FIELD && taken.length > 0) {
      return taken[0];
    }
    if (sent === null || entered[name] !== sent[name]) {
      return undefined;
    }
    const said = problems.filter((problem) => problem.field === name);
    return said.length === 0 ? undefined : said.map((problem) => problem.message).join("; ");
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (taken.length > 0) {
      return;
    }
    setSent(entered);
    // The simulator checks the values, and says by field what it refuses.
    onDraft(formValues(fields, entered) as unknown as BasicSetup);
  }

  return (
    <form className="builder-form" aria-labelledby={heading} onSubmit={submit}>
      <h2 id={heading}>A new house</h2>
      {fields.map((field) => (
        <Field
          key={field.name}
          label={field.title}
          problem={problemOf(field.name)}
          size="compact"
          className="builder-field"
        >
          {(control) =>
            field.kind === "choice" ? (
              <select
                {...control}
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
                {...control}
                name={field.name}
                type={field.kind === "text" ? "text" : "number"}
                step={field.kind === "integer" ? 1 : "any"}
                min={field.minimum}
                max={field.maximum}
                required={field.required}
                value={entered[field.name] ?? ""}
                onChange={(event) => setEntered({ ...entered, [field.name]: event.target.value })}
              />
            )
          }
        </Field>
      ))}
      <Button
        type="submit"
        size="compact"
        disabled={busy || taken.length > 0}
        aria-describedby={describedBy(why, taken)}
      >
        Draft this house
      </Button>
      <WhyNot id={why} lead="It cannot be drafted:" reasons={taken} testId="builder-draft-why" />
      {refused !== undefined && (
        <Notice kind="problem" className="builder-refused" data-testid="builder-draft-refused">
          The house cannot be drafted: {refused}
        </Notice>
      )}
    </form>
  );
}
