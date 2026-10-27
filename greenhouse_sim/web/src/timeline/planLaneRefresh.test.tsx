// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { click, render } from "../testing/render";
import { TimelinePanel } from "./TimelinePanel";

const RUN = { runId: "climate_box-climate-0f00ba11", epoch: 0, startedAt: "2026-03-01T00:00:00Z" };
const NO_OUTCOMES = {
  run_id: RUN.runId,
  epoch: 0,
  after: 0,
  next: 0,
  simulated_now: "2026-03-01T06:00:00Z",
  has_more: false,
  outcomes: [],
};

function answering(): { fetchFn: typeof fetch; asked: string[] } {
  const asked: string[] = [];
  const fetchFn = vi.fn(async (url: string) => {
    asked.push(url);
    if (url.includes("/outcomes")) {
      return new Response(JSON.stringify(NO_OUTCOMES));
    }
    return new Response(JSON.stringify(url.includes("/actions") ? [] : {}));
  });
  return { fetchFn: fetchFn as unknown as typeof fetch, asked };
}

async function settled(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("a followed run's plan lane, read again", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("once the viewer has given the run a plan, though its clock has not moved", async () => {
    const { fetchFn, asked } = answering();
    vi.stubGlobal("fetch", fetchFn);
    const shown = render(
      <TimelinePanel
        scenarioId="climate_box"
        run={{}}
        time={21_600}
        played={{ ...RUN, version: 0 }}
      />,
    );
    const summary = shown.container.querySelector("summary");
    expect(summary).not.toBeNull();
    act(() => click(summary as HTMLElement));
    await settled();
    const read = () => asked.filter((url) => url.includes("/outcomes")).length;
    const first = read();
    expect(first).toBeGreaterThan(0);

    shown.rerender(
      <TimelinePanel
        scenarioId="climate_box"
        run={{}}
        time={21_600}
        played={{ ...RUN, version: 0 }}
      />,
    );
    await settled();
    expect(read()).toBe(first);

    shown.rerender(
      <TimelinePanel
        scenarioId="climate_box"
        run={{}}
        time={21_600}
        played={{ ...RUN, version: 1 }}
      />,
    );
    await settled();
    expect(read()).toBeGreaterThan(first);
  });
});
