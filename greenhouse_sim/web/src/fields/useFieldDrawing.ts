import { useMemo, useState } from "react";

import type { ScalarRange } from "../debug/scalar";
import type { ScenarioRun } from "../scene/run";
import type { SceneSource } from "../scene/source";
import { drawn, useLoad, useLoadProgress } from "../useLoad";
import type { FieldView } from "./display";
import { defaultSlice, type HeldRanges, heldThrough, quantityScale } from "./drawing";
import { fetchField, fieldUrl } from "./source";

/**
 * A scenario's field, drawn over its scene, another compared with it at the
 * probes, and how the field is drawn: the last of each stays on show until
 * the next arrives, and the field's when the next fails.
 *
 * Its colours run over air speed for arrows and streamlines, and over the
 * slice's quantity for a slice, within a range the viewer chose, or else the
 * widest a climate run's moments have reached so far (`climateRun`, the run
 * apart from its moment), so that a slice keeps its colours as the run plays
 * and goes back; another run starts afresh.
 */
export function useFieldDrawing(
  source: SceneSource,
  run: ScenarioRun | null,
  climateRun: string | null,
) {
  // A range the viewer chose for the field's colours, in place of its own.
  const [fieldRange, setFieldRange] = useState<ScalarRange | null>(null);
  // The colour ranges a climate run's moments have reached, so far.
  const [heldRanges, setHeldRanges] = useState<HeldRanges | null>(null);
  const fieldName = source.kind === "scenario" ? (source.field ?? null) : null;
  const fieldProgress = useLoadProgress(
    run === null || fieldName === null ? null : fieldUrl(run.scenarioId, fieldName, run),
    fetchField,
    {
      onAnswer: (state) => {
        if (climateRun !== null && state.status === "loaded") {
          setHeldRanges((held) => heldThrough(held, climateRun, state.field));
        }
      },
    },
  );
  const field = drawn(fieldProgress);
  const compareName = source.kind === "scenario" ? (source.compare ?? null) : null;
  const compared = useLoad(
    run === null || compareName === null ? null : fieldUrl(run.scenarioId, compareName, run),
    fetchField,
  );

  const fieldView: FieldView =
    source.kind === "scenario" ? (source.fieldView ?? "arrows") : "arrows";
  const loadedField = field.status === "loaded" ? field.field : null;
  // Worked out once for each field and choice, not on every render: the
  // layers redraw, and trace streamlines afresh, whenever these change.
  const askedSlice = source.kind === "scenario" ? source.slice : undefined;
  const fieldSlice = useMemo(
    () =>
      fieldView === "slice" && loadedField !== null
        ? (askedSlice ?? defaultSlice(loadedField))
        : null,
    [fieldView, loadedField, askedSlice],
  );
  const scaleQuantity = fieldSlice === null ? "speed" : fieldSlice.quantity;
  const fieldScale = useMemo(
    () => (loadedField === null ? null : quantityScale(loadedField, scaleQuantity)),
    [loadedField, scaleQuantity],
  );
  const heldRange =
    heldRanges !== null && heldRanges.run === climateRun
      ? heldRanges.ranges[scaleQuantity]
      : undefined;
  const fieldColours = fieldScale === null ? null : (fieldRange ?? heldRange ?? fieldScale.range);
  return {
    fieldProgress,
    field,
    compared,
    fieldView,
    loadedField,
    fieldSlice,
    scaleQuantity,
    fieldScale,
    fieldColours,
    setFieldRange,
  };
}
