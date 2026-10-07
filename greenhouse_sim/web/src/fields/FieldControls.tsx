import { useEffect, useState } from "react";

import { formatValue } from "../readouts";
import { FIELD_VIEWS, type FieldView, SLICE_AXES, type Slice, type SliceQuantity } from "./display";
import { sliceQuantities } from "./drawing";
import { sliceExtent } from "./slice";
import { type FieldState, layoutQuery } from "./source";

// The choice of drawing no field.
const NO_FIELD = "";
// A slice moves in steps of this many metres.
const SLICE_STEP_M = 0.05;

/** The fields a scenario offers with one of its layouts, and which is its own
 * airflow (`GET /api/scenarios/{id}/fields`), or none if they cannot be read. */
export async function loadFieldNames(
  scenarioId: string,
  layout?: string,
  fetchFn: typeof fetch = fetch,
): Promise<{ names: string[]; configured: string | null }> {
  try {
    const response = await fetchFn(
      `/api/scenarios/${encodeURIComponent(scenarioId)}/fields${layoutQuery(layout)}`,
    );
    const body: unknown = response.ok ? await response.json() : null;
    if (typeof body !== "object" || body === null) {
      return { names: [], configured: null };
    }
    const names = "fields" in body && Array.isArray(body.fields) ? body.fields : [];
    const configured = "configured" in body ? body.configured : null;
    return {
      names: names.filter((name) => typeof name === "string"),
      configured: typeof configured === "string" ? configured : null,
    };
  } catch {
    return { names: [], configured: null };
  }
}

/** Which of the scenario's environment fields is drawn over its scene, how,
 * and what the drawn one holds. */
export function FieldControls({
  scenarioId,
  layout,
  chosen,
  state,
  view,
  slice,
  onChoose,
  onView,
  onSlice,
}: {
  scenarioId: string;
  /** Another of its layouts, if one is shown. */
  layout?: string | undefined;
  chosen: string | null;
  state: FieldState;
  view: FieldView;
  /** The slice drawn, when the view is a slice. */
  slice: Slice | null;
  onChoose: (field: string | null) => void;
  onView: (view: FieldView) => void;
  onSlice: (slice: Slice) => void;
}) {
  const [names, setNames] = useState<string[]>([]);
  const [configured, setConfigured] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    void loadFieldNames(scenarioId, layout).then((loaded) => {
      if (current) {
        setNames(loaded.names);
        setConfigured(loaded.configured);
      }
    });
    return () => {
      current = false;
    };
  }, [scenarioId, layout]);

  if (names.length === 0 && chosen === null) {
    return null;
  }
  const field = state.status === "loaded" ? state.field : null;
  const extent = field !== null && slice !== null ? sliceExtent(field.grid, slice.axis) : null;
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
              {name === configured ? `${name}, the scenario's airflow` : name}
            </option>
          ))}
        </select>
      </label>
      {chosen !== null && (
        <div className="field-views" role="radiogroup" aria-label="Drawn as">
          {FIELD_VIEWS.map((option) => (
            <label key={option}>
              <input
                type="radio"
                name="field-view"
                checked={view === option}
                onChange={() => onView(option)}
              />{" "}
              {option}
            </label>
          ))}
        </div>
      )}
      {field !== null && slice !== null && extent !== null && (
        <div className="field-slice">
          <label>
            Slice of{" "}
            <select
              value={slice.quantity}
              onChange={(event) =>
                onSlice({ ...slice, quantity: event.target.value as SliceQuantity })
              }
            >
              {sliceQuantities(field).map((quantity) => (
                <option key={quantity} value={quantity}>
                  {quantity === "speed" ? "air speed" : quantity}
                </option>
              ))}
            </select>
          </label>{" "}
          <label>
            square to{" "}
            <select
              value={slice.axis}
              onChange={(event) => {
                const axis = event.target.value as Slice["axis"];
                const range = sliceExtent(field.grid, axis);
                onSlice({ ...slice, axis, position: (range.min + range.max) / 2 });
              }}
            >
              {SLICE_AXES.map((axis) => (
                <option key={axis} value={axis}>
                  {axis}
                </option>
              ))}
            </select>
          </label>
          <label className="field-slice-position">
            at
            <input
              type="range"
              aria-label="Slice position"
              min={extent.min}
              max={extent.max}
              step={SLICE_STEP_M}
              value={slice.position}
              onChange={(event) => onSlice({ ...slice, position: Number(event.target.value) })}
            />
            <span data-testid="field-slice-position">
              {slice.axis} = {formatValue(slice.position)} m
            </span>
          </label>
        </div>
      )}
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
