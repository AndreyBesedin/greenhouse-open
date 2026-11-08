import { describe, expect, it, vi } from "vitest";

import { loadRoom, ROOM_URL, type Room, roomFigures, roomRefusalText } from "./room";

const ROOM: Room = {
  workers_busy: 2,
  workers_limit: 2,
  runs_waiting: 3,
  runs_waiting_limit: 200,
  disk_free_bytes: 45_200_000_000,
  disk_free_limit_bytes: 2_000_000_000,
  refusal: null,
};

function answering(body: unknown, status = 200): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("the room for runs", () => {
  it("is asked of the simulator and read as its contract says", async () => {
    const fetchFn = answering(ROOM);

    await expect(loadRoom(fetchFn)).resolves.toEqual({ status: "loaded", room: ROOM });
    expect(fetchFn).toHaveBeenCalledWith(ROOM_URL);
  });

  it("cannot be read from an answer that is not one, or a refusal, which it says in words", async () => {
    await expect(loadRoom(answering({ workers_busy: 1 }))).resolves.toEqual({
      status: "unavailable",
      reason: "the room for runs is not what the viewer reads",
    });
    const refused = answering(
      { error: "this simulator keeps no runs: it was made with no run store" },
      404,
    );
    await expect(loadRoom(refused)).resolves.toEqual({
      status: "unavailable",
      reason: "this simulator keeps no runs: it was made with no run store",
    });
  });

  it("says each figure beside its limit", () => {
    expect(roomFigures(ROOM)).toEqual([
      { label: "Workers", value: "2 of 2 busy" },
      { label: "Waiting", value: "3 runs, of 200 runs that may wait" },
      { label: "Free disk", value: "45.2 GB, and a run begins only with 2.0 GB" },
    ]);
  });

  it("says one run in the singular, none as none, and a limit that is none as none", () => {
    const loose: Room = {
      ...ROOM,
      runs_waiting: 1,
      runs_waiting_limit: null,
      disk_free_limit_bytes: null,
    };
    expect(roomFigures(loose).map((each) => each.value)).toEqual([
      "2 of 2 busy",
      "1 run, with no limit",
      "45.2 GB, with no floor",
    ]);
    expect(roomFigures({ ...ROOM, runs_waiting: 0, runs_waiting_limit: 1 })[1]?.value).toBe(
      "none, of 1 run that may wait",
    );
  });

  it("says a disk whose free space the store cannot say is not known", () => {
    expect(roomFigures({ ...ROOM, disk_free_bytes: null })[2]?.value).toBe(
      "not known, and a run begins only with 2.0 GB",
    );
  });

  it("says the refusal a run would be given in the simulator's words, and nothing if none", () => {
    const refusal =
      "3 runs waiting for a worker, and this simulator lets 3 runs wait: ask again once some have begun, or raise that limit";

    expect(roomRefusalText(ROOM)).toBeNull();
    expect(roomRefusalText({ ...ROOM, refusal })).toBe(
      `A run asked for now is refused: ${refusal}.`,
    );
  });
});
