import { useEffect } from "react";

import { CLIMATE_FIELD } from "../fields/source";
import { withTime } from "./edits";
import type { SceneSource } from "./source";
import type { SetSource } from "./useSource";

const MINUTE_S = 60;

/** The moment a replay draws for a position's: its whole minute, as runs are
 * drawn on whole minutes. */
export function replayedMoment(timeS: number): number {
  return Math.floor(timeS / MINUTE_S) * MINUTE_S;
}

/**
 * The moment a replay's position stands at (P17.6) as the moment drawn: moved
 * on once the moment asked for before has arrived, so that a position that
 * moves faster than the simulator answers is never drawn half over; a moment
 * whose field failed has arrived as far as it will, and the view moves on.
 * Only the climate field is asked for a moment (`fieldUrl`): any other field
 * the view draws is the layout's and says no moment, so nothing is waited for
 * and the replay is never held by it.
 * The run's own play stands aside (`onClockMoved`), as it does for a run
 * followed as it is played back.
 */
export function useReplayMoment({
  momentS,
  source,
  setSource,
  field,
  fieldShownMoment,
  fieldFailed,
  onClockMoved,
}: {
  /** The position's moment, or null while there is none. */
  momentS: number | null;
  source: SceneSource;
  setSource: (change: SetSource) => void;
  /** The field drawn over the scene, by name, or null for none. */
  field: string | null;
  fieldShownMoment: number | null;
  fieldFailed: boolean;
  onClockMoved: () => void;
}) {
  const waitsForField = field === CLIMATE_FIELD;
  const asked = source.kind === "scenario" ? (source.time ?? 0) : null;
  useEffect(() => {
    if (momentS === null || asked === null || momentS === asked) {
      return;
    }
    if (waitsForField && fieldShownMoment !== asked && !fieldFailed) {
      return;
    }
    onClockMoved();
    setSource((current) => (current.kind === "scenario" ? withTime(current, momentS) : current));
  }, [momentS, asked, waitsForField, fieldShownMoment, fieldFailed, onClockMoved, setSource]);
}
