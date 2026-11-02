import { useCallback, useEffect, useState } from "react";

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
 */
export function useReplay(runId: string, epoch: number, fetchFn: typeof fetch = fetch) {
  const [load, setLoad] = useState<PositionLoad>(LOADING);
  const positionId = load.status === "loaded" ? load.position.position_id : null;
  const moving =
    load.status === "loaded" &&
    (load.position.playing || load.position.following || isComputing(load.position.status));

  useEffect(() => {
    let left = false;
    let opened: string | null = null;
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
      void askPosition(positionId, fetchFn, { signal: controller.signal }).then(
        (answer) => {
          // A failed ask is asked again; the last good state stays.
          if (answer.status === "loaded" && !controller.signal.aborted) {
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
    void answered.then((answer) => {
      // A refused command leaves the position where it stood.
      if (answer.status === "loaded") {
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
