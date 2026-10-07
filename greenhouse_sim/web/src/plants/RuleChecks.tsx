import { useEffect, useState } from "react";

import { type ChecksState, loadLabChecks } from "./checks";
import { type LabRun, labRunQuery } from "./lab";

/** Whether every plant of the run keeps the structure's rules on the day on
 * show, and changed since the day before only as a plant may; if not, which
 * plants do not, and why. */
export function RuleChecks({ run }: { run: LabRun }) {
  const [state, setState] = useState<ChecksState>({ status: "loading" });
  const query = labRunQuery(run);

  // The last answer stays on show until this run's arrives.
  useEffect(() => {
    let current = true;
    void loadLabChecks(query).then((loaded) => {
      if (current) {
        setState(loaded);
      }
    });
    return () => {
      current = false;
    };
  }, [query]);

  switch (state.status) {
    case "loading":
      return <p data-testid="rule-checks">Checking the plants' structure…</p>;
    case "unavailable":
      return (
        <p data-testid="rule-checks" role="alert">
          The plants' structure could not be checked: {state.reason}.
        </p>
      );
    case "loaded": {
      const wrong = Object.entries(state.problems).filter(([, problems]) => problems.length > 0);
      const plants = Object.keys(state.problems).length;
      if (wrong.length === 0) {
        return (
          <p data-testid="rule-checks">
            On day {state.day}, all {plants} plants keep the structure's rules.
          </p>
        );
      }
      return (
        <div data-testid="rule-checks" role="alert">
          <p>
            On day {state.day}, {wrong.length} of {plants} plants break the structure's rules:
          </p>
          <ul>
            {wrong.map(([plantId, problems]) => (
              <li key={plantId}>
                {plantId}: {problems.join("; ")}
              </li>
            ))}
          </ul>
        </div>
      );
    }
  }
}
