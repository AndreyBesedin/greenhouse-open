import { refusal } from "../builder/api";
import { contractReader, loadJson } from "../loadJson";
import { ROOM_SCHEMA } from "./generated/roomSchema";
import type { Room } from "./generated/roomTypes";
import { sizeText } from "./storedRuns";

export type { Room };

/** What a run asked for now has room for (`GET /api/room`, P18.5): the workers
 * busy, the runs waiting and the disk free, each beside its limit. */
export const ROOM_URL = "/api/room";

export type RoomState =
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; room: Room };

const readRoom = contractReader<Room>(
  ROOM_SCHEMA,
  "the room for runs is not what the viewer reads",
);

/** Asks the simulator what room it has for runs; any failure becomes
 * `unavailable`. */
export async function loadRoom(fetchFn: typeof fetch = fetch): Promise<RoomState> {
  const answer = await loadJson(ROOM_URL, readRoom, fetchFn, refusal);
  return answer.status === "loaded" ? { status: "loaded", room: answer.value } : answer;
}

function runs(count: number): string {
  return count === 1 ? "1 run" : `${count} runs`;
}

/** One figure of the room, in words: what it is, and its value beside its limit. */
export interface RoomFigure {
  label: string;
  value: string;
}

/** The room, figure by figure, each beside its limit or the want of one. */
export function roomFigures(room: Room): RoomFigure[] {
  const waiting = room.runs_waiting === 0 ? "none" : runs(room.runs_waiting);
  const free = room.disk_free_bytes === null ? "not known" : sizeText(room.disk_free_bytes);
  return [
    { label: "Workers", value: `${room.workers_busy} of ${room.workers_limit} busy` },
    {
      label: "Waiting",
      value:
        room.runs_waiting_limit === null
          ? `${waiting}, with no limit`
          : `${waiting}, of ${runs(room.runs_waiting_limit)} that may wait`,
    },
    {
      label: "Free disk",
      value:
        room.disk_free_limit_bytes === null
          ? `${free}, with no floor`
          : `${free}, and a run begins only with ${sizeText(room.disk_free_limit_bytes)}`,
    },
  ];
}

/** What a run asked for now would be told, in the simulator's words; nothing if
 * there is room for it. */
export function roomRefusalText(room: Room): string | null {
  return room.refusal === null ? null : `A run asked for now is refused: ${room.refusal}.`;
}
