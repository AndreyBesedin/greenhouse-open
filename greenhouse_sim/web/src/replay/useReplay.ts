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

/** Whether an epoch is still being computed. */
function isComputing(status: string): boolean {
  return status === "queued" || status === "running";
}

/**
 * A stored epoch replayed (P17.6, decision 0065): a position opened over it
 * when the page is, kept in step with the simulator while it plays, follows
 * or its epoch is computed, and closed when the page is left. A position is
 * the viewer's place and not the epoch's clock, so what the viewer does
 * here changes nothing a consumer reads.
 *
 * A page that is shown twice, as the development server's strict mode does,
 * opens two positions and closes the first.
 *
 * What the simulator answers is taken in the order it was asked, never in
 * the order it arrives: a seek, a command or a pace is the page's latest
 * word on where the position stands, so an answer to an earlier one, or to a
 * look that began before it, or to anything asked of a replay that is no
 * longer the page's, is dropped. Dragging the handle asks for a seek at every
 * move; only the last one's answer is kept.
 */
export function useReplay(runId: string, epoch: number, fetchFn: typeof fetch = fetch) {
  const [load, setLoad] = useState<PositionLoad>(LOADING);
  // Counts what has been asked of the replay shown: each change of the replay,
  // and each seek, command or pace. An answer counts only if nothing was asked
  // after the question it answers.
  const asked = useRef(0);
  // How many of those are still waiting for their answer: a look that comes
  // back while one is, may have been answered before it.
  const waiting = useRef(0);
  const positionId = load.status === "loaded" ? load.position.position_id : null;
  const moving =
    load.status === "loaded" &&
    (load.position.playing || load.position.following || isComputing(load.position.status));

  useEffect(() => {
    let left = false;
    let opened: string | null = null;
    asked.current += 1;
    waiting.current = 0;
    setLoad(LOADING);
    // Not aborted once asked: a position the simulator has opened is closed,
    // however late its answer comes.
    void openPosition(runId, epoch, fetchFn).then((answer) => {
      if (answer.status === "loaded") {
        opened = answer.position.position_id;
        if (left) {
          void closePosition(opened, fetchFn);
          return;
        }
      }
      if (!left) {
        setLoad(answer);
      }
    });
    return () => {
      left = true;
      asked.current += 1;
      if (opened !== null) {
        void closePosition(opened, fetchFn);
      }
    };
  }, [runId, epoch, fetchFn]);

  useEffect(() => {
    if (positionId === null || !moving) {
      return;
    }
    const controller = new AbortController();
    const timer = setInterval(() => {
      const since = asked.current;
      void askPosition(positionId, fetchFn, { signal: controller.signal }).then(
        (answer) => {
          // A failed look is made again; the last good state stays. A look
          // that began before something was asked, or that comes back while
          // something asked waits, may say less than the page knows.
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
      // A refused command leaves the position where it stood.
      if (answer.status === "loaded" && asked.current === ticket) {
        setLoad(answer);
      }
    });
  }, []);
  return {
    load,
    command: (command: PositionCommand) => {
      if (positionId !== null) {
        keep(commandPosition(positionId, command, fetchFn));
      }
    },
    seek: (timeS: number) => {
      if (positionId !== null) {
        keep(seekPosition(positionId, timeS, fetchFn));
      }
    },
    pace: (secondsPerDay: number) => {
      if (positionId !== null) {
        keep(paceOfPosition(positionId, secondsPerDay, fetchFn));
      }
    },
  };
}
