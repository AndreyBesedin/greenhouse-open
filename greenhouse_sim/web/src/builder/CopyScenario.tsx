import { type FormEvent, useId, useState } from "react";

import type { ScenarioSummary } from "../scenarios";

/**
 * A scenario's house as a start (P12.2): copied under an identifier of its
 * own, so that the scenario itself is never changed, and edited as any
 * draft is.
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

  function copy(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (scenario !== undefined) {
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
          onChange={(event) => setDraftId(event.target.value)}
        />
      </div>
      <button type="submit" disabled={busy}>
        Copy its house
      </button>
    </form>
  );
}
