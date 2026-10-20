import { contractCheck } from "../loadJson";
import { checkScene } from "./checkScene";
import { LIVE_SCHEMA } from "./generated/liveSchema";
import type { LiveState } from "./generated/liveTypes";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** One simulated day of a live scenario, as `GET /api/scenarios/{id}/live` sends it. */
export interface LiveFrame {
  sequence: number;
  day: number;
  /** The simulated instant, ISO 8601 in UTC. */
  timestamp: string;
  playing: boolean;
  /** How many times faster than the simulator's own pace the run plays. */
  speed: number;
  snapshot: SceneSnapshot;
}

/** The speeds a live run plays at, as `SPEEDS` in `greenhouse_sim/api/live.py` lists them. */
// biome-ignore lint/style/noMagicNumbers: the list is the named value, mirroring the simulator's.
export const LIVE_SPEEDS: readonly number[] = [0.25, 0.5, 1, 2, 4, 8];

/** What the viewer can ask of a live run. Every viewer sees the result. */
export type LiveCommand = "play" | "pause" | "step" | "reset" | { speed: number };

export type CommandResult = { ok: true } | { ok: false; problem: string };

/** Whether the viewer is receiving the stream. A lost stream is retried. */
export type LiveConnection = "connecting" | "live" | "disconnected";

export type FrameCheck = { ok: true; frame: LiveFrame } | { ok: false; problems: string[] };

export function liveUrl(scenarioId: string): string {
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/live`;
}

export function commandUrl(scenarioId: string, command: LiveCommand): string {
  const live = liveUrl(scenarioId);
  return typeof command === "string"
    ? `${live}/${command}`
    : `${live}/speed?multiplier=${command.speed}`;
}

/**
 * Sends a command to a scenario's live run (`POST /api/scenarios/{id}/live/...`).
 * The run's new state arrives on the stream like any other frame, so the
 * answer only says whether the command was taken.
 */
export async function sendLiveCommand(
  scenarioId: string,
  command: LiveCommand,
  fetchFn: typeof fetch = fetch,
): Promise<CommandResult> {
  let response: Response;
  try {
    response = await fetchFn(commandUrl(scenarioId, command), { method: "POST" });
  } catch {
    return { ok: false, problem: "the simulator could not be reached" };
  }
  return response.ok ? { ok: true } : { ok: false, problem: await refusal(response) };
}

async function refusal(response: Response): Promise<string> {
  const answered = `the simulator answered ${response.status}`;
  try {
    const body: unknown = await response.json();
    const error =
      typeof body === "object" && body !== null ? (body as Record<string, unknown>).error : null;
    return typeof error === "string" ? `${answered}: ${error}` : answered;
  } catch {
    return answered;
  }
}

// A frame is the run's state with its scene, which the scene's own contract
// checks.
const checkState = contractCheck<LiveState & { snapshot?: unknown }>(LIVE_SCHEMA, "the frame");

/** A frame's event data, checked rather than trusted, scene included: the
 * run's state as its contract says, and its scene as the scene's does. */
export function parseLiveFrame(data: string): FrameCheck {
  let body: unknown;
  try {
    body = JSON.parse(data);
  } catch {
    return { ok: false, problems: ["the frame is not JSON"] };
  }
  const state = checkState(body);
  if (!state.ok) {
    return state;
  }
  const { sequence, day, timestamp, playing, speed, snapshot } = state.value;
  const scene = checkScene(snapshot);
  if (!scene.ok) {
    return scene;
  }
  return {
    ok: true,
    frame: { sequence, day, timestamp, playing, speed, snapshot: scene.snapshot },
  };
}
