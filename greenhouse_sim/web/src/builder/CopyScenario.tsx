import { type FormEvent, useId, useState } from "react";

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
  busy,
  onCopy,
}: {
  scenarios: readonly ScenarioSummary[];
  busy: boolean;
  onCopy: (scenario: ScenarioSummary, draftId: string) => void;
}) {
  const heading = useId();
  const [chosen, setChosen] = useState("");
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
      <div className="builder-field">
        <label htmlFor={`${heading}-scenario`}>Scenario</label>
        <select
          id={`${heading}-scenario`}
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
      </div>
      <div className="builder-field">
        <label htmlFor={`${heading}-draft`}>The copy's identifier</label>
        <input
          id={`${heading}-draft`}
          required
          value={named}
          aria-invalid={!valid}
          aria-describedby={valid ? undefined : `${heading}-draft-hint`}
          onChange={(event) => setDraftId(event.target.value)}
        />
        {valid ? null : (
          <p id={`${heading}-draft-hint`} className="builder-note">
            An identifier holds letters, digits, '_', '.' and '-' only.
          </p>
        )}
      </div>
      <button type="submit" disabled={busy || !valid}>
        Copy its house
      </button>
    </form>
  );
}
