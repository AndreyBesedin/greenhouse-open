import type { SceneEntity } from "../scene/generated/snapshotTypes";
import { organOf, plantOf } from "../selection";
import { type GrowthSpeed, LabControls } from "./LabControls";
import { type LabRun, PLANT_LAB_FIRST_PLANT } from "./lab";
import { PlantActions } from "./PlantActions";
import { PlantStructure } from "./PlantStructure";
import { RuleChecks } from "./RuleChecks";

/**
 * The plant lab's panels, in the info panel's order: its run and its play,
 * whether its plants keep the structure's rules, the crop work scheduled,
 * and the structure of the plant selected, or of its first.
 */
export function LabPanels({
  run,
  shownDay,
  selected,
  playing,
  speed,
  showNames,
  onRun,
  onPlaying,
  onSpeed,
  onShowNames,
  onSelectOrgan,
}: {
  run: LabRun;
  /** The day of the scene on show, if one is. */
  shownDay: number | null;
  /** The selected entity, if one is. */
  selected: SceneEntity | null;
  playing: boolean;
  speed: GrowthSpeed;
  showNames: boolean;
  onRun: (change: Partial<LabRun>) => void;
  onPlaying: (playing: boolean) => void;
  onSpeed: (speed: GrowthSpeed) => void;
  onShowNames: (showNames: boolean) => void;
  onSelectOrgan: (organId: string) => void;
}) {
  return (
    <>
      <LabControls
        run={run}
        shownDay={shownDay}
        onChange={onRun}
        playing={playing}
        speed={speed}
        showNames={showNames}
        onPlaying={onPlaying}
        onSpeed={onSpeed}
        onShowNames={onShowNames}
      />
      <RuleChecks run={run} />
      <PlantActions
        entity={selected}
        day={run.day}
        scheduled={run.actions.length}
        onAct={(action) => onRun({ actions: [...run.actions, action] })}
        onUndo={() => onRun({ actions: run.actions.slice(0, -1) })}
        onClear={() => onRun({ actions: [] })}
      />
      <PlantStructure
        plant={{ ...run, plantId: plantOf(selected) ?? PLANT_LAB_FIRST_PLANT }}
        selectedOrgan={selected === null ? null : organOf(selected)}
        onSelect={onSelectOrgan}
      />
    </>
  );
}
