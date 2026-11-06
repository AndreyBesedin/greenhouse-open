import { refusal } from "../builder/api";
import { contractCheck } from "../loadJson";
import { POSITION_SCHEMA } from "../scene/generated/positionSchema";
import type { PositionState } from "../scene/generated/positionTypes";

export type { PositionState };

/** A position over a stored epoch, as the simulator says it stands, or why it
 * cannot be said (P17.4, decision 0065). `gone` says the simulator does not know
 * what was asked for, as once it has started again, rather than that it could not
 * answer just then. */
export type PositionLoad =
  | { status: "loading" }
  | { status: "unavailable"; reason: string; gone?: boolean }
  | { status: "loaded"; position: PositionState };

/** What a viewer asks a position to do. */
export type PositionCommand = "play" | "pause" | "follow";

const NOT_FOUND = 404;

const checkPosition = contractCheck<PositionState>(POSITION_SCHEMA, "the position");

/** A stored epoch's address: the epoch as the list of runs shows it, and the root of its routes. */
export function epochUrl(runId: string, epoch: number): string {
  return `/api/runs/${encodeURIComponent(runId)}/epochs/${epoch}`;
}

function positionUrl(positionId: string, action = "", query = ""): string {
  return `/api/positions/${encodeURIComponent(positionId)}${action}${query}`;
}

/** The position in an answer, checked rather than trusted. */
async function read(response: Response): Promise<PositionLoad> {
  if (!response.ok) {
    return {
      status: "unavailable",
      reason: await refusal(response),
      ...(response.status === NOT_FOUND ? { gone: true } : {}),
    };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const checked = checkPosition(body);
  return checked.ok
    ? { status: "loaded", position: checked.value }
    : { status: "unavailable", reason: "the position's state is not what the viewer reads" };
}

async function send(url: string, init: RequestInit, fetchFn: typeof fetch): Promise<PositionLoad> {
  try {
    return await read(await fetchFn(url, init));
  } catch (error) {
    if (init.signal?.aborted) {
      throw error;
    }
    return { status: "unavailable", reason: "the simulator could not be reached" };
  }
}

/** Opens a position at the start of a stored epoch. */
export function openPosition(
  runId: string,
  epoch: number,
  fetchFn: typeof fetch = fetch,
  init: RequestInit = {},
): Promise<PositionLoad> {
  return send(`${epochUrl(runId, epoch)}/positions`, { ...init, method: "POST" }, fetchFn);
}

/** Where a position stands now. */
export function askPosition(
  positionId: string,
  fetchFn: typeof fetch = fetch,
  init: RequestInit = {},
): Promise<PositionLoad> {
  return send(positionUrl(positionId), init, fetchFn);
}

/** Plays, pauses or follows the frontier. */
export function commandPosition(
  positionId: string,
  command: PositionCommand,
  fetchFn: typeof fetch = fetch,
): Promise<PositionLoad> {
  return send(positionUrl(positionId, `/${command}`), { method: "POST" }, fetchFn);
}

/** Moves a position to a moment, from the start to the frontier. */
export function seekPosition(
  positionId: string,
  timeS: number,
  fetchFn: typeof fetch = fetch,
): Promise<PositionLoad> {
  return send(positionUrl(positionId, "/seek", `?t=${timeS}`), { method: "POST" }, fetchFn);
}

/** Sets how many real seconds a simulated day plays in. */
export function paceOfPosition(
  positionId: string,
  secondsPerDay: number,
  fetchFn: typeof fetch = fetch,
): Promise<PositionLoad> {
  return send(
    positionUrl(positionId, "/pace", `?seconds_per_day=${secondsPerDay}`),
    { method: "POST" },
    fetchFn,
  );
}

/** Closes a position that nobody looks at any more. The answer is not read. */
export async function closePosition(
  positionId: string,
  fetchFn: typeof fetch = fetch,
): Promise<void> {
  try {
    await fetchFn(positionUrl(positionId, "/close"), { method: "POST", keepalive: true });
  } catch {
    // Nothing waits on it.
  }
}
