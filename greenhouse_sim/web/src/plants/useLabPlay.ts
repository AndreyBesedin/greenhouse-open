import { useEffect, useState } from "react";

import type { SceneSource } from "../scene/source";
import type { SetSource } from "../scene/useSource";
import type { GrowthSpeed } from "./LabControls";
import { PLANT_LAB_LAST_DAY } from "./lab";

const MILLISECONDS_PER_SECOND = 1000;

/**
 * The plant lab's play, and its speed in days a second: playing, the lab
 * moves on a day once the day asked for is on show (`shownDay`), at most as
 * fast as its speed, and stops on its last day.
 */
export function useLabPlay(
  source: SceneSource,
  shownDay: number | null,
  setSource: (change: SetSource) => void,
) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<GrowthSpeed>(1);
  const labDay = source.kind === "plants" ? source.day : null;
  useEffect(() => {
    if (!playing || labDay === null || shownDay !== labDay) {
      return;
    }
    if (labDay >= PLANT_LAB_LAST_DAY) {
      setPlaying(false);
      return;
    }
    const next = window.setTimeout(() => {
      setSource((current) => {
        if (current.kind !== "plants") {
          return current;
        }
        return { ...current, day: labDay + 1 };
      });
    }, MILLISECONDS_PER_SECOND / speed);
    return () => window.clearTimeout(next);
  }, [playing, labDay, shownDay, speed, setSource]);
  return { playing, setPlaying, speed, setSpeed };
}
