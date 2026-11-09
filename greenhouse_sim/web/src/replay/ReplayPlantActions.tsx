import type { LabAction } from "../plants/lab";
import { PlantActions } from "../plants/PlantActions";
import type { SceneEntity } from "../scene/generated/snapshotTypes";
import { useForkQuestion } from "./useForkQuestion";

/**
 * A plant's work in a replay (P22.3, decision 0074): a leaf removed, a fruit or
 * a truss harvested, or the stem lowered, on the selected organ's plant. While
 * the epoch is being computed it is asked of it (`onWork`), and its worker
 * carries it out as soon as it can, at its own clock. Once the epoch has ended,
 * it is a fork from the moment shown (`onFork`), asked first, as any fork is.
 */
export function ReplayPlantActions({
  entity,
  computing,
  onWork,
  onFork,
}: {
  /** The selected entity, if one is. */
  entity: SceneEntity | null;
  /** Whether the epoch is being computed, so that the work steers it. */
  computing: boolean;
  onWork: (action: LabAction) => void;
  onFork: (action: LabAction) => void;
}) {
  const { ask, question } = useForkQuestion({ about: entity?.entity_id ?? "" });
  return (
    <>
      <PlantActions
        entity={entity}
        day={0}
        scheduled={0}
        onAct={(action) => (computing ? onWork(action) : ask(() => onFork(action)))}
      />
      {question}
    </>
  );
}
