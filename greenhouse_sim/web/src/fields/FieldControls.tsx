import { useEffect, useState } from "react";

import { formatValue } from "../readouts";
import type { FieldState } from "./source";

// The choice of drawing no field.
const NO_FIELD = "";

/** The fields a scenario offers (`GET /api/scenarios/{id}/fields`), or none
 * if they cannot be read. */
async function loadFieldNames(scenarioId: string, fetchFn: typeof fetch = fetch) {
  try {
    const response = await fetchFn(`/api/scenarios/${encodeURIComponent(scenarioId)}/fields`);
    const body: unknown = response.ok ? await response.json() : null;
    const names =
      typeof body === "object" && body !== null && "fields" in body ? body.fields : null;
    return Array.isArray(names) ? names.filter((name) => typeof name === "string") : [];
  } catch {
    return [];
  }
}

/** Which of the scenario's environment fields is drawn over its scene, and
 * what the drawn one holds. */
export function FieldControls({
  scenarioId,
  chosen,
  state,
  onChoose,
}: {
  scenarioId: string;
  chosen: string | null;
  state: FieldState;
  onChoose: (field: string | null) => void;
}) {
  const [names, setNames] = useState<string[]>([]);

  useEffect(() => {
    let current = true;
    void loadFieldNames(scenarioId).then((loaded) => {
      if (current) {
        setNames(loaded);
      }
    });
    return () => {
      current = false;
    };
  }, [scenarioId]);

  if (names.length === 0 && chosen === null) {
    return null;
  }
  return (
    <fieldset className="field-controls" aria-label="Air field">
      <label>
        Air field{" "}
        <select
          value={chosen ?? NO_FIELD}
          onChange={(event) =>
            onChoose(event.target.value === NO_FIELD ? null : event.target.value)
          }
        >
          <option value={NO_FIELD}>none</option>
          {names.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <p data-testid="field-status">{describeState(state)}</p>
    </fieldset>
  );
}

function describeState(state: FieldState): string {
  switch (state.status) {
    case "none":
      return "No field drawn.";
    case "loading":
      return "Loading the field…";
    case "unavailable":
      return `The field is not available: ${state.reason}.`;
    case "rejected":
      return `The field was refused: ${state.problems.join("; ")}.`;
    case "loaded": {
      const { field } = state;
      const { cells } = field.grid;
      const velocity = field.channels.velocity;
      const speeds =
        velocity === undefined
          ? ""
          : `, air speed ${formatValue(velocity.minimum)} to ${formatValue(velocity.maximum)} ${velocity.unit}`;
      return `${field.fieldId} (${field.source}): ${cells.x} × ${cells.y} × ${cells.z} cells${speeds}.`;
    }
  }
}
