import { describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { deleteRun, notDeleted } from "./runActions";
import type { StoredRun } from "./storedRuns";

const RUN: StoredRun = {
  run_id: "reference_greenhouse-climate-abc",
  epoch: 2,
  scenario_id: "reference_greenhouse",
  seed: 1,
  layout: "default",
  weather: null,
  status: "running",
  frontier_s: DAY_S,
  duration_s: 120 * DAY_S,
  progress: 1 / 120,
  created_at: "2026-10-28T09:30:00Z",
  size_bytes: 1024,
  start_s: 0,
  fork: null,
  stopping: false,
  damaged: false,
  days_computed: 1,
  cpu_s: null,
  peak_memory_bytes: null,
  wall_s: null,
  past_limit: false,
  reason: null,
};
const DELETE = "/api/runs/reference_greenhouse-climate-abc/epochs/2/delete";
const STOP = "/api/runs/reference_greenhouse-climate-abc/epochs/2/stop";
const COMPUTED = { status: 409, body: { error: "being computed" } };

type Answer = { status: number; body: unknown };

/** The simulator, stood in for: each address answers the next of its answers,
 * the last again once they run out, and what was asked is kept in order. */
function simulator(answers: Record<string, Answer[]>) {
  const asked: string[] = [];
  const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    asked.push(url);
    const these = answers[url] ?? [];
    const answer = (these.length > 1 ? these.shift() : these[0]) ?? { status: 404, body: {} };
    return new Response(JSON.stringify(answer.body), { status: answer.status });
  });
  return { asked, fetchFn: fetchFn as typeof fetch };
}

describe("deleting a run", () => {
  it("deletes a run that is over in one ask", async () => {
    const { asked, fetchFn } = simulator({ [DELETE]: [{ status: 200, body: {} }] });

    expect(await deleteRun(RUN, fetchFn)).toEqual({ ok: true, value: null });
    expect(asked).toEqual([DELETE]);
  });

  it("stops a run being computed first, then deletes it", async () => {
    const { asked, fetchFn } = simulator({
      [DELETE]: [COMPUTED, { status: 200, body: {} }],
      [STOP]: [{ status: 200, body: { ...RUN, status: "interrupted" } }],
    });

    expect(await deleteRun(RUN, fetchFn)).toEqual({ ok: true, value: null });
    expect(asked).toEqual([DELETE, STOP, DELETE]);
  });

  it("says a run is stopping when its worker has not looked yet", async () => {
    const { asked, fetchFn } = simulator({
      [DELETE]: [COMPUTED],
      [STOP]: [{ status: 200, body: { ...RUN, stopping: true } }],
    });

    expect(await deleteRun(RUN, fetchFn)).toBe("stopping");
    expect(asked).toEqual([DELETE, STOP]);
  });

  it("takes a run gone as deleted, and one ended before its stop as one to delete", async () => {
    const gone = simulator({ [DELETE]: [COMPUTED], [STOP]: [{ status: 404, body: {} }] });
    expect(await deleteRun(RUN, gone.fetchFn)).toEqual({ ok: true, value: null });

    const ended = simulator({
      [DELETE]: [COMPUTED, { status: 200, body: {} }],
      [STOP]: [{ status: 409, body: { error: "it is not being computed" } }],
    });
    expect(await deleteRun(RUN, ended.fetchFn)).toEqual({ ok: true, value: null });
    expect(ended.asked).toEqual([DELETE, STOP, DELETE]);
  });

  it("says why a stop was refused, if the run is still being computed", async () => {
    const { fetchFn } = simulator({
      [DELETE]: [COMPUTED],
      [STOP]: [{ status: 500, body: { error: "the store is read-only" } }],
    });

    const answer = await deleteRun(RUN, fetchFn);

    expect(answer).toMatchObject({ ok: false });
    expect(answer !== "stopping" && !answer.ok && answer.problem).toContain(
      "the store is read-only",
    );
  });

  it("says why a run is not deleted yet, as its row reads", () => {
    expect(notDeleted({ status: "running" }, "this run")).toBe(
      "This run is stopping: it can be deleted once it reads Interrupted.",
    );
    expect(notDeleted({ status: "queued" }, "this run")).toBe(
      "This run is stopping: it can be deleted once it reads Interrupted.",
    );
    expect(notDeleted({ status: "interrupted" }, "this run")).toBe(
      "This run is still being written: try again.",
    );
  });
});
