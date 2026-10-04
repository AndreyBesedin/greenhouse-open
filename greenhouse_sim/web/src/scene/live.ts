import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** One simulated day of a live scenario, as `GET /api/scenarios/{id}/live` sends it. */
export interface LiveFrame {
  sequence: number;
  day: number;
  /** The simulated instant, ISO 8601 in UTC. */
  timestamp: string;
  snapshot: SceneSnapshot;
}

/** Whether the viewer is receiving the stream. A lost stream is retried. */
export type LiveConnection = "connecting" | "live" | "disconnected";

export type FrameCheck = { ok: true; frame: LiveFrame } | { ok: false; problems: string[] };

export function liveUrl(scenarioId: string): string {
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/live`;
}

/** A frame's event data, checked rather than trusted, scene included. */
export function parseLiveFrame(data: string): FrameCheck {
  let body: unknown;
  try {
    body = JSON.parse(data);
  } catch {
    return { ok: false, problems: ["the frame is not JSON"] };
  }
  if (typeof body !== "object" || body === null) {
    return { ok: false, problems: ["the frame is not an object"] };
  }
  const fields = body as Record<string, unknown>;
  if (
    !Number.isInteger(fields.sequence) ||
    !Number.isInteger(fields.day) ||
    typeof fields.timestamp !== "string"
  ) {
    return { ok: false, problems: ["the frame has no sequence, day or timestamp"] };
  }
  const scene = checkScene(fields.snapshot);
  if (!scene.ok) {
    return { ok: false, problems: scene.problems };
  }
  return {
    ok: true,
    frame: {
      sequence: fields.sequence as number,
      day: fields.day as number,
      timestamp: fields.timestamp,
      snapshot: scene.snapshot,
    },
  };
}
