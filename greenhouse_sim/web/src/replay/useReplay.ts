import { useCallback, useEffect, useRef, useState } from "react";

import {
  askPosition,
  closePosition,
  commandPosition,
  openPosition,
  type PositionCommand,
  type PositionLoad,
  paceOfPosition,
  seekPosition,
} from "./position";

// How often a replay asks where its position stands, while it moves or its
// epoch is still being computed.
const POLL_MS = 1000;
const LOADING: PositionLoad = { status: "loading" };
/** Why a replay stands still once the simulator has let its position go: positions
 * are held in its memory, and the page's names none after it has started again. */
export const POSITION_LOST = "the simulator has started again and no longer holds this replay";

/** The seeks of one position: whether one is on its way, and the moment asked
 * for since, to send when it is answered. */
interface Seeks {
  onItsWay: boolean;
  next: number | null;
}

/** Whether an epoch is still being computed. */
function isComputing(status: string): boolean {
  return status === "queued" || status === "running";
}

/**
 * A stored epoch replayed (P17.6, decision 0065): a position opened over it
 * when the page is, kept in step with the simulator while it plays or its
 * epoch is computed, and closed when the page is left. A position is
 * the viewer's place and not the epoch's clock, so what the viewer does
 * here changes nothing a consumer reads.
 *
 * A page that is shown twice, as the development server's strict mode does,
 * opens two positions and closes the first. One asked to open `following` is
 * shown first at the newest day computed, and not on its way there.
 *
 * What the simulator answers is taken in the order it was asked, never in
 * the order it arrives: a seek, a command or a pace is the page's latest
 * word on where the position stands, so an answer to an earlier one, or to a
 * look that began before it, or to anything asked of a replay that is no
 * longer the page's, is dropped.
 *
 * One seek is on its way at a time, and only the latest asked for since is
 * sent after it: dragging the handle asks at every move, and a seek the
 * simulator has begun restoring a checkpoint for goes on whether the page
 * still wants it or not, so a drag sends what the simulator keeps up with.
 */
export function useReplay(
  runId: string,
  epoch: number,
  fetchFn: typeof fetch = fetch,
  following = false,
) {
  const [load, setLoad] = useState<PositionLoad>(LOADING);
  // Why the latest seek, command or pace did nothing, if it was refused.
  const [refused, setRefused] = useState<string | null>(null);
  // Whether the simulator has let the position go: nothing more can be asked of it.
  const [lost, setLost] = useState(false);
  // The moment last sought, until the latest thing asked is answered: the keys and
  // the buttons move from it, so that a second press does not start from where the
  // position stood before the first. Answered, or refused, the position says again.
  const [heading, setHeading] = useState<number | null>(null);
  // Counts what has been asked of the replay shown: each change of the replay,
  // and each seek, command or pace. An answer counts only if nothing was asked
  // after the question it answers.
  const asked = useRef(0);
  // How many of those are still waiting for their answer: a look that comes
  // back while one is, may have been answered before it.
  const waiting = useRef(0);
  const seeks = useRef<Seeks>({ onItsWay: false, next: null });
  const positionId = load.status === "loaded" ? load.position.position_id : null;
  // A position that follows moves only while its epoch is computed: one that
  // followed an epoch to its end stays following, at a frontier that moves no more.
  const moving =
    !lost &&
    load.status === "loaded" &&
    (load.position.playing || isComputing(load.position.status));

  useEffect(() => {
    let left = false;
    let opened: string | null = null;
    asked.current += 1;
    waiting.current = 0;
    seeks.current = { onItsWay: false, next: null };
    setLoad(LOADING);
    setRefused(null);
    setLost(false);
    setHeading(null);
    // Not aborted once asked: a position the simulator has opened is closed,
    // however late its answer comes.
    void openPosition(runId, epoch, fetchFn).then(async (answer) => {
      if (answer.status !== "loaded") {
        if (!left) {
          setLoad(answer);
        }
        return;
      }
      opened = answer.position.position_id;
      if (left) {
        void closePosition(opened, fetchFn);
        return;
      }
      const moved = following ? await commandPosition(opened, "follow", fetchFn) : answer;
      if (left) {
        return;
      }
      // Not following is no reason not to show the run, where it was opened.
      setLoad(moved.status === "loaded" ? moved : answer);
      if (moved.status === "unavailable") {
        setRefused(moved.reason);
      }
    });
    return () => {
      left = true;
      asked.current += 1;
      seeks.current.next = null;
      if (opened !== null) {
        void closePosition(opened, fetchFn);
      }
    };
  }, [runId, epoch, fetchFn, following]);

  useEffect(() => {
    if (positionId === null || !moving) {
      return;
    }
    const controller = new AbortController();
    const timer = setInterval(() => {
      const since = asked.current;
      void askPosition(positionId, fetchFn, { signal: controller.signal }).then(
        (answer) => {
          // A failed look is made again and the last good state stays, unless
          // the simulator no longer has the position, which no look brings back.
          // A look that began before something was asked, or that comes back while
          // something asked waits, may say less than the page knows.
          if (answer.status === "unavailable" && answer.gone && !controller.signal.aborted) {
            setLost(true);
            setRefused(POSITION_LOST);
            return;
          }
          if (
            answer.status === "loaded" &&
            !controller.signal.aborted &&
            asked.current === since &&
            waiting.current === 0
          ) {
            setLoad(answer);
          }
        },
        () => undefined,
      );
    }, POLL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [positionId, moving, fetchFn]);

  const keep = useCallback((answered: Promise<PositionLoad>) => {
    asked.current += 1;
    waiting.current += 1;
    const ticket = asked.current;
    void answered.then((answer) => {
      waiting.current = Math.max(0, waiting.current - 1);
      if (asked.current !== ticket) {
        return;
      }
      setHeading(null);
      // A refused command leaves the position where it stood, and says so:
      // the simulator has let the position go, or cannot be reached, and a
      // control that only did nothing would look broken.
      if (answer.status === "loaded") {
        setLoad(answer);
        setRefused(null);
      } else if (answer.status === "unavailable") {
        setRefused(answer.reason);
      }
    });
  }, []);
  const send = useCallback(
    (position: string, timeS: number, line: Seeks) => {
      line.onItsWay = true;
      const answered = seekPosition(position, timeS, fetchFn);
      keep(answered);
      void answered.finally(() => {
        line.onItsWay = false;
        if (line.next !== null) {
          const next = line.next;
          line.next = null;
          send(position, next, line);
        }
      });
    },
    [fetchFn, keep],
  );
  return {
    load,
    refused,
    heading,
    command: (command: PositionCommand) => {
      if (positionId !== null) {
        if (command === "follow") {
          // Following is a later word than any seek still to be sent.
          seeks.current.next = null;
        }
        keep(commandPosition(positionId, command, fetchFn));
      }
    },
    seek: (timeS: number) => {
      if (positionId === null) {
        return;
      }
      setHeading(timeS);
      const line = seeks.current;
      if (line.onItsWay) {
        // The answer on its way is to an earlier word than this.
        asked.current += 1;
        line.next = timeS;
      } else {
        send(positionId, timeS, line);
      }
    },
    pace: (secondsPerDay: number) => {
      if (positionId !== null) {
        keep(paceOfPosition(positionId, secondsPerDay, fetchFn));
      }
    },
  };
}
