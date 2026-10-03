import { useEffect, useState } from "react";

import { type LiveConnection, type LiveFrame, liveUrl, parseLiveFrame } from "./live";
import type { SceneState } from "./source";

// After an error response, such as a 502 from the dev server's proxy while the
// API is down, EventSource gives up for good; the viewer tries again itself.
const RECONNECT_AFTER_MS = 1000;

export interface LiveScene {
  connection: LiveConnection;
  frame: LiveFrame | null;
  scene: SceneState;
}

/** Follows a scenario's live stream while `scenarioId` is set. */
export function useLiveScene(scenarioId: string | null): LiveScene {
  const [connection, setConnection] = useState<LiveConnection>("connecting");
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [scene, setScene] = useState<SceneState>({ status: "none" });

  useEffect(() => {
    if (scenarioId === null) {
      return;
    }
    let events: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    setConnection("connecting");
    setFrame(null);
    setScene({ status: "loading" });

    function connect(id: string): void {
      const source = new EventSource(liveUrl(id));
      events = source;
      source.onopen = () => setConnection("live");
      source.onerror = () => {
        setConnection("disconnected");
        if (source.readyState === EventSource.CLOSED) {
          retry = setTimeout(() => connect(id), RECONNECT_AFTER_MS);
        }
      };
      source.addEventListener("frame", (event) => {
        const check = parseLiveFrame((event as MessageEvent<string>).data);
        if (check.ok) {
          setConnection("live");
          setFrame(check.frame);
          setScene({ status: "loaded", snapshot: check.frame.snapshot });
        } else {
          setScene({ status: "rejected", problems: check.problems });
        }
      });
    }

    connect(scenarioId);
    return () => {
      events?.close();
      if (retry !== null) {
        clearTimeout(retry);
      }
    };
  }, [scenarioId]);

  return { connection, frame, scene };
}
