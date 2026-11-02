// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { ScenarioSummary } from "../scenarios";
import { type Rendered, render } from "../testing/render";
import { Landing } from "./Landing";
import { followAddress, REPOSITORY_URL, viewerAddress } from "./paths";
import type { StoredRun } from "./storedRuns";

// What the simulator sends of a scenario besides its name: how it grows its
// crop, its daily commands, openings and weathers, its opening day and heater.
const SENT = {
  crop_model: "simple",
  daily: [],
  openings: [],
  weathers: ["default"],
  opening_day: null,
  thermostat: null,
};
const SCENARIOS: ScenarioSummary[] = [
  {
    ...SENT,
    id: "reference_greenhouse",
    name: "Reference greenhouse",
    description: "organ-level tomato crop",
    plants: 32,
    duration_days: 120,
    layouts: ["default"],
  },
  {
    ...SENT,
    id: "tomgro_house",
    name: "TOMGRO house",
    description: "crop grown by area",
    plants: 0,
    duration_days: 120,
    layouts: ["default"],
  },
];

function run(more: Partial<StoredRun>): StoredRun {
  return {
    run_id: "reference_greenhouse-climate-abc",
    epoch: 0,
    scenario_id: "reference_greenhouse",
    seed: 1,
    layout: "default",
    status: "finished",
    frontier_s: 120 * DAY_S,
    duration_s: 120 * DAY_S,
    progress: 1,
    created_at: "2026-10-28T09:30:00Z",
    size_bytes: 1024,
    ...more,
  };
}

/** The simulator, stood in for: each address answers what it is given, or
 * fails if it is given an error. */
function simulator(answers: Record<string, unknown>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const answer = answers[String(input)];
      if (answer instanceof Error) {
        throw answer;
      }
      return new Response(JSON.stringify(answer), { status: answer === undefined ? 404 : 200 });
    }),
  );
}

describe("the page where a person decides what to do", () => {
  let page: Rendered | undefined;
  afterEach(() => {
    page?.unmount();
    vi.unstubAllGlobals();
  });

  async function shown(
    answers: Record<string, unknown>,
    waitFor: string,
  ): Promise<{ container: HTMLElement; navigate: ReturnType<typeof vi.fn> }> {
    simulator(answers);
    const navigate = vi.fn();
    page = render(<Landing navigate={navigate} />);
    const { container } = page;
    await vi.waitFor(() => expect(container.textContent).toContain(waitFor));
    return { container, navigate };
  }

  const link = (within: ParentNode, name: string) =>
    [...within.querySelectorAll("a")].find((each) => each.textContent?.trim() === name);

  it("links to the project's code in a page of its own, and to the builder", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [] },
      "No run has been kept yet",
    );

    const contribute = link(container, "Contribute");
    expect(contribute?.getAttribute("href")).toBe(REPOSITORY_URL);
    expect(contribute?.getAttribute("target")).toBe("_blank");
    expect(contribute?.getAttribute("rel")).toContain("noopener");
    expect(link(container, "Open the builder")?.getAttribute("href")).toBe("/builder");
  });

  it("opens the viewer on the scenario that is chosen, or the builder", async () => {
    const { container, navigate } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": [run({})] },
      "Reference greenhouse",
    );
    const input = container.querySelector("input");
    act(() => input?.click());
    const options = () => [...container.querySelectorAll('[role="option"]')];

    expect(options()[0]?.textContent).toContain("1 run");
    expect(options()[1]?.textContent).toContain("no runs");
    act(() => {
      options()[1]?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    });
    expect(navigate).toHaveBeenLastCalledWith(viewerAddress("tomgro_house"));

    act(() => input?.click());
    act(() => {
      options()
        .at(-1)
        ?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    });
    expect(navigate).toHaveBeenLastCalledWith("/builder");
  });

  it("lists the latest runs in words, and offers to follow only one still computing", async () => {
    const { container } = await shown(
      {
        "/api/scenarios": SCENARIOS,
        "/api/runs": [
          run({ epoch: 1, seed: 2, status: "running", frontier_s: 41 * DAY_S, progress: 41 / 120 }),
          run({
            scenario_id: "tomgro_house",
            seed: null,
            status: "interrupted",
            frontier_s: 63 * DAY_S,
          }),
          run({ epoch: 3, status: "failed", frontier_s: 5 * DAY_S, created_at: null }),
        ],
      },
      "Recent runs",
    );
    await vi.waitFor(() => expect(container.querySelectorAll(".landing-run")).toHaveLength(3));
    const rows = [...container.querySelectorAll(".landing-run")].map((row) => row.textContent);

    expect(rows[0]).toContain("Reference greenhouse");
    expect(rows[0]).toContain("seed 2 · epoch 1 · Oct 28");
    expect(rows[0]).toContain("Running");
    expect(rows[0]).toContain("41 of 120 days");
    expect(rows[1]).toContain("TOMGRO house");
    expect(rows[1]).toContain("the scenario's seed · epoch 0");
    expect(rows[1]).toContain("Interrupted");
    expect(rows[2]).toContain("Failed");
    expect(rows[2]).not.toContain("Oct");
    const follows = [...container.querySelectorAll("a")].filter(
      (each) => each.textContent === "Follow",
    );
    expect(follows.map((each) => each.getAttribute("href"))).toEqual([
      followAddress("reference_greenhouse"),
    ]);
  });

  it("lists no more than the latest few", async () => {
    const many = Array.from({ length: 8 }, (_, epoch) => run({ epoch }));
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": many },
      "epoch 0",
    );
    expect(container.querySelectorAll(".landing-run")).toHaveLength(5);
  });

  it("says so when the simulator cannot be reached, and when the runs cannot be listed", async () => {
    const { container } = await shown(
      { "/api/scenarios": new Error("offline"), "/api/runs": new Error("offline") },
      "The runs kept cannot be listed: offline.",
    );
    expect(container.textContent).toContain("The simulator API is not reachable (offline).");
    expect(link(container, "Open the builder")).toBeDefined();
  });

  it("keeps the scenarios usable when only the runs cannot be listed", async () => {
    const { container } = await shown(
      { "/api/scenarios": SCENARIOS, "/api/runs": new Error("no run store") },
      "The runs kept cannot be listed: no run store.",
    );
    const input = container.querySelector("input");
    act(() => input?.click());
    expect(container.querySelectorAll('[role="option"]')[0]?.textContent).toBe(
      "Reference greenhousereference_greenhouse · organ-level tomato crop",
    );
  });
});
