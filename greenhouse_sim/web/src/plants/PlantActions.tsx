import type { SceneEntity } from "../scene/generated/snapshotTypes";
import type { LabAction } from "./lab";

/** What can be done to the plant an entity draws part of, as of a day of the
 * lab's run: to the organ itself, to its truss, and to its stem. */
export function actionsFor(
  entity: SceneEntity,
  day: number,
): { label: string; action: LabAction }[] {
  const {
    organ_id: organId,
    organ_kind: kind,
    plant_id: plantId,
    truss_id: trussId,
  } = entity.properties;
  if (typeof organId !== "string" || typeof plantId !== "string") {
    return [];
  }
  const on = (kind: LabAction["kind"], target: string): LabAction => ({
    day,
    plantId,
    kind,
    target,
  });
  const choices: { label: string; action: LabAction }[] = [];
  if (kind === "leaf") {
    choices.push({ label: "Remove this leaf", action: on("remove_leaf", organId) });
  }
  if (kind === "fruit") {
    choices.push({ label: "Harvest this fruit", action: on("harvest_fruit", organId) });
  }
  if (typeof trussId === "string") {
    choices.push({ label: "Harvest its truss", action: on("harvest_truss", trussId) });
  }
  choices.push({ label: "Lower the stem", action: on("lower_stem", "1") });
  return choices;
}

/**
 * Actions on the selected organ's plant, scheduled at the start of the day on
 * show: they change it from then on, and the plant's history says what each
 * did, or why it was refused. The latest action can be taken back, or all.
 */
export function PlantActions({
  entity,
  day,
  scheduled,
  onAct,
  onUndo,
  onClear,
}: {
  /** The selected entity, if one is. */
  entity: SceneEntity | null;
  day: number;
  /** How many actions the run schedules already. */
  scheduled: number;
  onAct: (action: LabAction) => void;
  onUndo: () => void;
  onClear: () => void;
}) {
  const choices = entity === null ? [] : actionsFor(entity, day);
  if (choices.length === 0 && scheduled === 0) {
    return null;
  }
  return (
    <fieldset className="plant-actions" aria-label="Plant actions">
      {choices.map(({ label, action }) => (
        <button key={label} type="button" onClick={() => onAct(action)}>
          {label}
        </button>
      ))}
      {scheduled > 0 && (
        <>
          <button type="button" onClick={onUndo}>
            Take back the last action
          </button>
          <button type="button" onClick={onClear}>
            Take back all {scheduled}
          </button>
        </>
      )}
    </fieldset>
  );
}
