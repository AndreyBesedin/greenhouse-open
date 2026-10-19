// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sourceFromSearch } from "../scene/source";
import { button, type Rendered, render, said } from "../testing/render";
import { CheckpointsPanel, describeCheckpoint } from "./CheckpointsPanel";
import {
  type CheckpointSummary,
  downloadName,
  downloadUrl,
  loadCheckpoints,
  parseCheckpoint,
  restored,
  saveCheckpoint,
  saveUrl,
  uploadCheckpoint,
  weatherParts,
} from "./checkpoints";

// The reference run's second day's start, its heater set off an hour into
// its first day, under its own weather with the clouds overridden.
const BODY = {
  checkpoint_id: "a6c84f7670591ba5",
  scenario_id: "reference_greenhouse",
  layout: "default",
  weather: "default@80",
  levels: {},
  openings: { door: 1 },
  commands: [[3600, "heater", 0]],
  daily: null,
  day: 1,
  time_s: 86400,
  plants: 32,
};
const CHECKPOINT: CheckpointSummary = parseCheckpoint(BODY);

function answering(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("a checkpoint", () => {
  it("is checked rather than trusted", () => {
    expect(CHECKPOINT).toMatchObject({
      checkpointId: "a6c84f7670591ba5",
      commands: [{ timeS: 3600, actuatorId: "heater", level: 0 }],
      daily: null,
      day: 1,
      timeS: 86400,
    });
    expect(() => parseCheckpoint({ ...BODY, commands: [[1, 2, 3]] })).toThrow("not a moment");
    expect(() => parseCheckpoint({ ...BODY, day: "one" })).toThrow("not what the viewer expects");
  });

  it("is saved at a run's moment, downloaded by its name, and its weather read back", () => {
    expect(saveUrl("reference_greenhouse", { time: 90000, levels: { heater: 1 } })).toBe(
      "/api/scenarios/reference_greenhouse/checkpoints?set=heater:1&t=90000",
    );
    expect(downloadUrl(CHECKPOINT)).toBe("/api/checkpoints/a6c84f7670591ba5");
    expect(downloadName(CHECKPOINT)).toBe("reference_greenhouse-day-1-a6c84f7670591ba5.json");
    expect(weatherParts("default")).toEqual({});
    expect(weatherParts("cold_spring_day@80~90")).toEqual({
      weather: "cold_spring_day",
      clouds: 80,
      wind: 90,
    });
    expect(weatherParts("default~270")).toEqual({ wind: 270 });
  });

  it("is restored as its run at its moment, the view kept as it was", () => {
    const shown = sourceFromSearch(
      "?scenario=reference_greenhouse&field=climate&fieldView=slice&t=500000&schedule=400000:fan_left:0",
    );
    if (shown.kind !== "scenario") {
      throw new Error("not a scenario");
    }

    expect(restored(shown, CHECKPOINT, "climate")).toEqual({
      kind: "scenario",
      scenarioId: "reference_greenhouse",
      clouds: 80,
      openings: { door: 1 },
      field: "climate",
      fieldView: "slice",
      schedule: [{ timeS: 3600, actuatorId: "heater", level: 0 }],
      time: 86400,
    });
    expect(restored(shown, { ...CHECKPOINT, daily: [] }, "climate").daily).toEqual([]);
  });

  it("is listed, saved and uploaded, and a refusal says why", async () => {
    expect(await loadCheckpoints("/api/checkpoints", answering(200, [BODY]))).toEqual({
      status: "loaded",
      checkpoints: [CHECKPOINT],
    });
    const saving = answering(200, BODY);
    expect(await saveCheckpoint("/x", saving)).toEqual({ ok: true, checkpoint: CHECKPOINT });
    expect(saving).toHaveBeenCalledWith("/x", { method: "POST" });
    expect(
      await uploadCheckpoint("{}", answering(400, { error: "not a checkpoint: Field required" })),
    ).toEqual({ ok: false, problem: "not a checkpoint: Field required" });
  });
});

describe("the checkpoints panel", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  async function settle(): Promise<void> {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("lists the scenario's, saves the moment's day's start, and restores one", async () => {
    const other = { ...BODY, checkpoint_id: "b", scenario_id: "climate_box" };
    const kept: unknown[] = [other];
    const fetchFn = vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        kept.push(BODY);
        return new Response(JSON.stringify(BODY));
      }
      return new Response(JSON.stringify(kept));
    }) as unknown as typeof fetch;
    const onRestore = vi.fn();
    shown = render(
      <CheckpointsPanel
        scenarioId="reference_greenhouse"
        run={{ time: 90000 }}
        time={90000}
        onRestore={onRestore}
        fetchFn={fetchFn}
      />,
    );
    const details = shown.container.querySelector("details");
    if (details === null) {
      throw new Error("no details");
    }
    await act(async () => {
      details.open = true;
      details.dispatchEvent(new Event("toggle"));
    });
    await settle();
    expect(shown.container.textContent).toContain("None kept for this scenario.");

    await act(async () => button(details, "Save day 1's start").click());
    await settle();
    await settle();

    expect(fetchFn).toHaveBeenCalledWith(
      "/api/scenarios/reference_greenhouse/checkpoints?t=90000",
      { method: "POST" },
    );
    expect(said(details, "checkpoint-description")).toBe(describeCheckpoint(CHECKPOINT));
    expect(describeCheckpoint(CHECKPOINT)).toBe(
      "day 1: 1 commands before it, its scenario's daily commands, under default@80",
    );
    await act(async () => button(details, "Restore day 1, a6c84f7670591ba5").click());
    expect(onRestore).toHaveBeenCalledWith(CHECKPOINT);
  });

  it("gives up its list's request when it is closed, through the fetch it is given", async () => {
    let listing: AbortSignal | undefined;
    const fetchFn = vi.fn(async (_url: string, init?: RequestInit) => {
      listing = init?.signal ?? undefined;
      return new Promise<Response>(() => undefined);
    }) as unknown as typeof fetch;
    shown = render(
      <CheckpointsPanel
        scenarioId="reference_greenhouse"
        run={{ time: 90000 }}
        time={90000}
        onRestore={vi.fn()}
        fetchFn={fetchFn}
      />,
    );
    const details = shown.container.querySelector("details");
    if (details === null) {
      throw new Error("no details");
    }
    async function toggle(open: boolean): Promise<void> {
      await act(async () => {
        if (details !== null) {
          details.open = open;
          details.dispatchEvent(new Event("toggle"));
        }
      });
    }

    await toggle(true);
    expect(listing?.aborted).toBe(false);
    await toggle(false);

    expect(listing?.aborted).toBe(true);
  });
});
