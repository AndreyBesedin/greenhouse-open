import { useCallback, useEffect, useRef, useState } from "react";

import { loadPlayback, type PlaybackLoad } from "../scene/playback";
import type { Action } from "./generated/planTypes";
import { giveToPlan, setLevel, setTarget } from "./plan";

// How long a slider rests before the levels it set go to the run: one
// revision for a drag, not one for each step of it.
export const STEER_PAUSE_MS = 300;
// How close a level shown is to one asked for to be it, past the decimal
// text the address writes it in.
const SAME_LEVEL = 1e-9;

/**
 * A run followed as it plays, steered from the viewer's panels (P13.8): the
 * levels set wait until no more are set for `STEER_PAUSE_MS`, then go to the
 * run's gateway together, as the next revision of the viewer's plan
 * (`giveToPlan`); targets go at once. Each level asked for is `asked` until
 * the panels show it (`shown`, the levels the run has at its clock), or it
 * is refused; a refusal is `refusal`, in the gateway's words, until the next
 * change is given; and `given` counts the plans given, for what reads them.
 * Once given, the playback is read again (`onPlayback`), so that the view
 * draws the run with what it was given.
 */
export function useSteering(
  scenarioId: string | null,
  shown: Readonly<Record<string, number>>,
  onPlayback: (load: PlaybackLoad) => void,
  fetchFn: typeof fetch = fetch,
) {
  const [asked, setAsked] = useState<Readonly<Record<string, number>>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  // How many times the run has been given a plan, accepted or refused: what
  // reads the plan reads it again after each.
  const [given, setGiven] = useState(0);
  const waiting = useRef<Record<string, number>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const give = useCallback(
    async (actions: Action[]): Promise<boolean> => {
      if (scenarioId === null || actions.length === 0) {
        return false;
      }
      const answer = await giveToPlan(scenarioId, actions, fetchFn);
      setRefusal(answer.status === "refused" ? answer.reason : null);
      setGiven((count) => count + 1);
      onPlayback(await loadPlayback(scenarioId, fetchFn));
      return answer.status === "given";
    },
    [scenarioId, onPlayback, fetchFn],
  );

  const flush = useCallback(async () => {
    timer.current = null;
    const levels = waiting.current;
    waiting.current = {};
    const given = await give(
      Object.entries(levels).map(([deviceId, level]) => setLevel(deviceId, level)),
    );
    if (!given) {
      setAsked((current) => without(current, levels));
    }
  }, [give]);

  /** Sets devices' levels, from the run's clock on. */
  const steer = useCallback(
    (levels: Readonly<Record<string, number>>) => {
      waiting.current = { ...waiting.current, ...levels };
      setAsked((current) => ({ ...current, ...levels }));
      stopWaiting(timer);
      timer.current = setTimeout(() => void flush(), STEER_PAUSE_MS);
    },
    [flush],
  );

  /** Sets heating targets, from the run's next minute on. */
  const setTargets = useCallback(
    (targets: Readonly<Record<string, number>>) =>
      void give(Object.entries(targets).map(([target, valueC]) => setTarget(target, valueC))),
    [give],
  );

  // A level asked for stops being one once it is shown.
  useEffect(() => {
    setAsked((current) => {
      const shownNow = Object.fromEntries(
        Object.entries(current).filter(([deviceId, level]) => {
          const standing = shown[deviceId];
          return standing !== undefined && Math.abs(standing - level) < SAME_LEVEL;
        }),
      );
      return Object.keys(shownNow).length === 0 ? current : without(current, shownNow);
    });
  }, [shown]);

  // Another run followed, or none: nothing asked of the one before, nor
  // waiting to be given it.
  const steered = useRef(scenarioId);
  useEffect(() => {
    if (steered.current === scenarioId) {
      return;
    }
    steered.current = scenarioId;
    stopWaiting(timer);
    waiting.current = {};
    setAsked({});
    setRefusal(null);
  }, [scenarioId]);
  useEffect(() => () => stopWaiting(timer), []);

  return { asked, refusal, given, steer, setTargets };
}

/** `levels` without the devices `gone` names, as long as they are asked for
 * at the same level still. */
function without(
  levels: Readonly<Record<string, number>>,
  gone: Readonly<Record<string, number>>,
): Readonly<Record<string, number>> {
  return Object.fromEntries(
    Object.entries(levels).filter(([deviceId, level]) => gone[deviceId] !== level),
  );
}

function stopWaiting(timer: { current: ReturnType<typeof setTimeout> | null }): void {
  if (timer.current !== null) {
    clearTimeout(timer.current);
    timer.current = null;
  }
}
