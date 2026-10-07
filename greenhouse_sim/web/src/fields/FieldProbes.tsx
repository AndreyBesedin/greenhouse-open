import { useEffect, useState } from "react";

import { formatValue } from "../readouts";
import type { Point3 } from "../world";
import { loadFieldNames } from "./FieldControls";
import type { EnvironmentField } from "./field";
import {
  type Difference,
  difference,
  MAX_PROBES,
  middleOf,
  type Reading,
  readingAt,
  type ScalarQuantity,
} from "./probes";
import type { FieldState } from "./source";

// The choice of comparing with no field.
const NO_FIELD = "";
// A probe's coordinates, and the height clicks place probes at, move in
// steps of this many metres.
const PROBE_STEP_M = 0.05;

// Probes' values are read to hundredths, every one alike.
const PROBE_DECIMALS = 2;

/** A probe's value to hundredths, a negative one that rounds to nothing
 * without its sign. */
export function probeValue(value: number): string {
  const text = value.toFixed(PROBE_DECIMALS);
  return Number(text) === 0 ? (0).toFixed(PROBE_DECIMALS) : text;
}

function signed(value: number): string {
  const text = probeValue(value);
  return Number(text) > 0 ? `+${text}` : text;
}

function unitOf(field: EnvironmentField, quantity: ScalarQuantity): string {
  return field.channels[quantity]?.unit ?? "";
}

/** A reading as a line of text: the air's speed and velocity, then each
 * scalar with its unit. */
export function readingText(field: EnvironmentField, reading: Reading): string {
  if (reading.velocity === null && Object.keys(reading.scalars).length === 0) {
    return "outside the field";
  }
  const parts: string[] = [];
  if (reading.velocity !== null && reading.speed !== null) {
    const { x, y, z } = reading.velocity;
    const unit = field.channels.velocity?.unit ?? "";
    parts.push(`${probeValue(reading.speed)} ${unit} (${[x, y, z].map(probeValue).join(", ")})`);
  }
  for (const [quantity, value] of Object.entries(reading.scalars)) {
    parts.push(
      `${quantity} ${probeValue(value)} ${unitOf(field, quantity as ScalarQuantity)}`.trim(),
    );
  }
  return parts.join(", ");
}

/** How one reading differs from another, as a line of text. */
export function differenceText(field: EnvironmentField, change: Difference): string {
  const parts: string[] = [];
  if (change.speed !== null) {
    parts.push(`${signed(change.speed)} ${field.channels.velocity?.unit ?? ""}`.trim());
  }
  if (change.turnDeg !== null) {
    parts.push(`turned ${probeValue(change.turnDeg)}°`);
  }
  for (const [quantity, value] of Object.entries(change.scalars)) {
    parts.push(`${quantity} ${signed(value)} ${unitOf(field, quantity as ScalarQuantity)}`.trim());
  }
  return parts.length === 0 ? "nothing to compare" : parts.join(", ");
}

function CoordinateInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <input
      aria-label={label}
      type="number"
      step={PROBE_STEP_M}
      value={formatValue(value)}
      onChange={(event) => {
        const next = Number(event.target.value);
        if (event.target.value !== "" && Number.isFinite(next)) {
          onChange(next);
        }
      }}
    />
  );
}

/** Points in the drawn field, what it says at each, and, if another of the
 * scenario's fields is chosen to compare with, what that one says and how
 * the drawn field differs from it. A probe is added in the field's middle,
 * or where the view is clicked while placing them. */
export function FieldProbes({
  scenarioId,
  layout,
  fieldName,
  field,
  compareName,
  compareState,
  probes,
  placing,
  height,
  onProbes,
  onCompare,
  onPlacing,
  onHeight,
}: {
  scenarioId: string;
  layout?: string | undefined;
  fieldName: string;
  field: EnvironmentField;
  compareName: string | null;
  compareState: FieldState;
  probes: readonly Point3[];
  /** Whether a click in the view places a probe, rather than selecting. */
  placing: boolean;
  /** How high a clicked probe is placed, above the ground under the click. */
  height: number;
  onProbes: (probes: Point3[]) => void;
  onCompare: (name: string | null) => void;
  onPlacing: (placing: boolean) => void;
  onHeight: (height: number) => void;
}) {
  const [names, setNames] = useState<string[]>([]);
  useEffect(() => {
    let current = true;
    void loadFieldNames(scenarioId, layout).then((loaded) => {
      if (current) {
        setNames(loaded.names);
      }
    });
    return () => {
      current = false;
    };
  }, [scenarioId, layout]);

  const compared = compareState.status === "loaded" ? compareState.field : null;
  const full = probes.length >= MAX_PROBES;
  const move = (index: number, change: Partial<Point3>) =>
    onProbes(probes.map((probe, at) => (at === index ? { ...probe, ...change } : probe)));
  return (
    <fieldset className="field-probes" aria-label="Probes">
      <p className="field-probes-actions">
        <button
          type="button"
          disabled={full}
          onClick={() => onProbes([...probes, middleOf(field)])}
        >
          Add a probe
        </button>{" "}
        <label>
          <input
            type="checkbox"
            checked={placing}
            disabled={full && !placing}
            onChange={(event) => onPlacing(event.target.checked)}
          />{" "}
          place by clicking, at
        </label>{" "}
        <input
          aria-label="Probe height"
          type="number"
          min={0}
          step={PROBE_STEP_M}
          value={formatValue(height)}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (event.target.value !== "" && Number.isFinite(next) && next >= 0) {
              onHeight(next);
            }
          }}
        />{" "}
        m
      </p>
      <label>
        Compare with{" "}
        <select
          value={compareName ?? NO_FIELD}
          onChange={(event) =>
            onCompare(event.target.value === NO_FIELD ? null : event.target.value)
          }
        >
          <option value={NO_FIELD}>none</option>
          {names
            .filter((name) => name !== fieldName)
            .map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
        </select>
      </label>
      {compareName !== null && compareState.status !== "loaded" && (
        <p data-testid="compare-status">
          {compareState.status === "loading"
            ? "Loading the field to compare with…"
            : `The field to compare with is not available.`}
        </p>
      )}
      {probes.length > 0 && (
        <table aria-label="Probe readings">
          <tbody>
            {probes.map((probe, index) => {
              const reading = readingAt(field, probe);
              const theirs = compared === null ? null : readingAt(compared, probe);
              const name = `P${index + 1}`;
              return (
                // biome-ignore lint/suspicious/noArrayIndexKey: probes are numbered by their place.
                <tr key={index} data-testid={`probe-${index + 1}`}>
                  <th scope="row">{name}</th>
                  <td>
                    <CoordinateInput
                      label={`${name} x`}
                      value={probe.x}
                      onChange={(x) => move(index, { x })}
                    />
                    <CoordinateInput
                      label={`${name} y`}
                      value={probe.y}
                      onChange={(y) => move(index, { y })}
                    />
                    <CoordinateInput
                      label={`${name} z`}
                      value={probe.z}
                      onChange={(z) => move(index, { z })}
                    />
                    <button
                      type="button"
                      aria-label={`Remove ${name}`}
                      onClick={() => onProbes(probes.filter((_, at) => at !== index))}
                    >
                      ✕
                    </button>
                    <div data-testid={`probe-${index + 1}-reading`}>
                      {fieldName}: {readingText(field, reading)}
                    </div>
                    {compared !== null && theirs !== null && compareName !== null && (
                      <>
                        <div data-testid={`probe-${index + 1}-compared`}>
                          {compareName}: {readingText(compared, theirs)}
                        </div>
                        <div data-testid={`probe-${index + 1}-difference`}>
                          {fieldName} − {compareName}:{" "}
                          {differenceText(field, difference(reading, theirs))}
                        </div>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </fieldset>
  );
}
