import { describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { failedText, loadFailure, NO_REASON_KEPT } from "./failure";
import { epochUrl } from "./position";

const FAILED = {
  run_id: "run 1",
  epoch: 2,
  scenario_id: "reference_greenhouse",
  seed: 7,
  layout: "default",
  status: "failed",
  paused: false,
  frontier_s: DAY_S,
  duration_s: 3 * DAY_S,
  progress: 1 / 3,
  created_at: null,
  size_bytes: 10,
  stopping: false,
  damaged: false,
  days_computed: 1,
  cpu_s: null,
  peak_memory_bytes: null,
  wall_s: null,
  past_limit: false,
  reason: "its worker ran out of memory",
  start_s: 0,
  fork: null,
};

function answering(body: unknown, status = 200): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("why a stored run failed", () => {
  it("is read from the epoch as the runs list it", async () => {
    const fetchFn = answering(FAILED);

    await expect(loadFailure(epochUrl("run 1", 2), fetchFn)).resolves.toEqual({
      status: "loaded",
      reason: "its worker ran out of memory",
    });
    expect(fetchFn).toHaveBeenCalledWith("/api/runs/run%201/epochs/2");
  });

  it("says the simulator kept none, for an epoch that failed before epochs said why", async () => {
    await expect(loadFailure("/run", answering({ ...FAILED, reason: null }))).resolves.toEqual({
      status: "loaded",
      reason: NO_REASON_KEPT,
    });
  });

  it("cannot be read from an answer that is not a run", async () => {
    const refused = await loadFailure("/run", answering({ detail: "no such run" }, 404));
    const unread = await loadFailure("/run", answering({ run_id: "run 1" }));

    expect(refused.status).toBe("unavailable");
    expect(unread).toEqual({
      status: "unavailable",
      reason: "the run's answer is not what the viewer reads",
    });
  });

  it("is said in a sentence, or only that it failed until it is read", () => {
    expect(failedText("its worker ran out of memory")).toBe(
      "This run failed: its worker ran out of memory.",
    );
    expect(failedText(null)).toBe("This run failed.");
  });
});
