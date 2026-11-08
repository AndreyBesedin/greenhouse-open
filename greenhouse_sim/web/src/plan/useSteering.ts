import { useCallback, useEffect, useRef, useState } from "react";

import { loadPlayback, type PlaybackLoad } from "../scene/playback";
import type { Action } from "./generated/planTypes";
import { type Given, giveToPlan, setLevel, setTarget } from "./plan";

// How long a slider rests before the levels it set go to the run: one
// revision for a drag, not one for each step of it.
export const STEER_PAUSE_MS = 300;
// How close a level shown is to one asked for to be it, past the decimal
// text the address writes it in.
const SAME_LEVEL = 1e-9;

/** How actions reach the run steered: given, from the moment it says if it
 * says one, or refused and why. */
export type Give = (actions: Action[]) => Promise<Given>;

/** How the panels give actions to the run a playback plays, through its plan
 * (P13.8): once given, the playback is read again (`onPlayback`), so that the
 * view draws the run with what it was given. */
export function useGiveToPlayback(
  scenarioId: string | null,
  onPlayback: (load: PlaybackLoad) => void,
  fetchFn: typeof fetch = fetch,
): Give {
  return useCallback(
    async (actions: Action[]) => {
      if (scenarioId === null) {
        return { status: "refused", reason: "no run is played back" };
      }
      const answer = await giveToPlan(scenarioId, actions, fetchFn);
      onPlayback(await loadPlayback(scenarioId, fetchFn));
      return answer;
    },
    [scenarioId, onPlayback, fetchFn],
  );
}

/**
 * A run steered from the viewer's panels as it is computed: one a playback
 * plays and the view follows (P13.8, `useGiveToPlayback`), or an epoch a
 * worker computes, from its replay (P22.1, `useGiveToEpoch`). `steered` names
 * it, null if none is; `give` is how actions reach it. The levels set wait
 * until no more are set for `STEER_PAUSE_MS`, then go to the run together;
 * targets, and what is asked of a plant, go at once. Each level asked for is
 * `asked` until the panels show it (`shown`, the levels the run has at the
 * moment they show), or it is refused; a refusal is `refusal`, in the run's
 * words, until the next change is given; `waiting` counts the changes on
 * their way and not yet answered; `taken` is the moment the latest change
 * given took effect from, where the run says it; and `given` counts the
 * changes given, for what reads them.
 */
export function useSteering(
  steered: string | null,
  shown: Readonly<Record<string, number>>,
  give: Give,
) {
  const [asked, setAsked] = useState<Readonly<Record<string, number>>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  // How many times the run has been given a change, accepted or refused:
  // what reads its plan reads it again after each.
  const [given, setGiven] = useState(0);
  const [waiting, setWaiting] = useState(0);
  const [taken, setTaken] = useState<number | null>(null);
  const resting = useRef<Record<string, number>>({});
  // The run steered as the latest render named it.
  const was = useRef(steered);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const send = useCallback(
    async (actions: Action[]): Promise<boolean> => {
      if (steered === null || actions.length === 0) {
        return false;
      }
      setWaiting((count) => count + 1);
      const answer = await give(actions);
      setWaiting((count) => count - 1);
      // What another run, steered since, says nothing of the one steered now.
      if (was.current !== steered) {
        return false;
      }
      setRefusal(answer.status === "refused" ? answer.reason : null);
      if (answer.status === "given" && answer.atS !== undefined) {
        setTaken(answer.atS);
      }
      setGiven((count) => count + 1);
      return answer.status === "given";
    },
    [steered, give],
  );

  const flush = useCallback(async () => {
    timer.current = null;
    const levels = resting.current;
    resting.current = {};
    const given = await send(
      Object.entries(levels).map(([deviceId, level]) => setLevel(deviceId, level)),
    );
    if (!given) {
      setAsked((current) => without(current, levels));
    }
  }, [send]);

  /** Sets devices' levels, from the run's clock on. */
  const steer = useCallback(
    (levels: Readonly<Record<string, number>>) => {
      resting.current = { ...resting.current, ...levels };
      setAsked((current) => ({ ...current, ...levels }));
      stopWaiting(timer);
      timer.current = setTimeout(() => void flush(), STEER_PAUSE_MS);
    },
    [flush],
  );

  /** Gives actions at once, as a plant's work is. */
  const act = useCallback((actions: Action[]) => void send(actions), [send]);

  /** Sets heating targets, from the run's next minute on. */
  const setTargets = useCallback(
    (targets: Readonly<Record<string, number>>) =>
      void send(Object.entries(targets).map(([target, valueC]) => setTarget(target, valueC))),
    [send],
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

  // Another run steered, or none: nothing asked of the one before, nor
  // waiting to be given it.
  useEffect(() => {
    if (was.current === steered) {
      return;
    }
    was.current = steered;
    stopWaiting(timer);
    resting.current = {};
    setAsked({});
    setRefusal(null);
    setTaken(null);
  }, [steered]);
  useEffect(() => () => stopWaiting(timer), []);

  return { asked, refusal, waiting, taken, given, steer, setTargets, act };
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
