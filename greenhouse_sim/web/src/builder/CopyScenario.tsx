import { type FormEvent, useId, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import { Notice } from "../design/Notice";
import type { ScenarioSummary } from "../scenarios";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";
import { keptAlready } from "./WhyNot";

// An installation's identifier, as the simulator checks it.
const IDENTIFIER = new RegExp(BASIC_SETUP_SCHEMA.properties.installation_id.pattern);

/**
 * A scenario's house as a start (P12.2): copied under an identifier of its
 * own, so that the scenario itself is never changed, and edited as any
 * draft is. An identifier the simulator would refuse is refused here, before
 * the copy is made, as is one a kept draft has, under which the copy could
 * never be saved; each is said at the field.
 */
export function CopyScenario({
  scenarios,
  first = "",
  busy,
  kept = [],
  refused,
  onCopy,
}: {
  scenarios: readonly ScenarioSummary[];
  /** The scenario chosen as it opens, as a runs dialog asks (P22.4): by
   * default, none: the first listed. */
  first?: string;
  busy: boolean;
  /** The identifiers of the drafts kept. */
  kept?: readonly string[];
  /** Why the last copy asked for could not be made, if it could not. */
  refused?: string | undefined;
  onCopy: (scenario: ScenarioSummary, draftId: string) => void;
}) {
  const heading = useId();
  const [chosen, setChosen] = useState(first);
  const [draftId, setDraftId] = useState("");
  const scenario = scenarios.find((each) => each.id === chosen) ?? scenarios[0];
  if (scenario === undefined) {
    return null;
  }
  const named = draftId === "" ? `${scenario.id}_copy` : draftId;
  const problem = !IDENTIFIER.test(named)
    ? "An identifier holds letters, digits, '_', '.' and '-' only."
    : kept.includes(named)
      ? keptAlready(named)
      : undefined;
  const valid = problem === undefined;

  function copy(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (scenario !== undefined && valid) {
      onCopy(scenario, named);
    }
  }

  return (
    <form className="builder-copy" aria-labelledby={heading} onSubmit={copy}>
      <h2 id={heading}>Or copy a scenario's house</h2>
      <Field label="Scenario" size="compact" className="builder-field">
        {(control) => (
          <select
            {...control}
            value={scenario.id}
            onChange={(event) => {
              setChosen(event.target.value);
              setDraftId("");
            }}
          >
            {scenarios.map((each) => (
              <option key={each.id} value={each.id}>
                {each.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field
        label="The copy's identifier"
        problem={problem}
        size="compact"
        className="builder-field"
      >
        {(control) => (
          <input
            {...control}
            required
            value={named}
            onChange={(event) => setDraftId(event.target.value)}
          />
        )}
      </Field>
      <Button type="submit" size="compact" disabled={busy || !valid}>
        Copy its house
      </Button>
      {refused !== undefined && (
        <Notice kind="problem" className="builder-refused" data-testid="builder-copy-refused">
          {refused}
        </Notice>
      )}
    </form>
  );
}
