import { type FormEvent, useId, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import type { ScenarioSummary } from "../scenarios";
import { BASIC_SETUP_SCHEMA } from "./generated/basicSchema";

// An installation's identifier, as the simulator checks it.
const IDENTIFIER = new RegExp(BASIC_SETUP_SCHEMA.properties.installation_id.pattern);

/**
 * A scenario's house as a start (P12.2): copied under an identifier of its
 * own, so that the scenario itself is never changed, and edited as any
 * draft is. An identifier the simulator would refuse is refused here, before
 * the copy is made.
 */
export function CopyScenario({
  scenarios,
  first = "",
  busy,
  onCopy,
}: {
  scenarios: readonly ScenarioSummary[];
  /** The scenario chosen as it opens, as a runs dialog asks (P22.4): by
   * default, none: the first listed. */
  first?: string;
  busy: boolean;
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
  const valid = IDENTIFIER.test(named);

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
        problem={valid ? undefined : "An identifier holds letters, digits, '_', '.' and '-' only."}
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
    </form>
  );
}
