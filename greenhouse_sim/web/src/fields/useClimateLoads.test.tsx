// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ScenarioRun } from "../scene/run";
import { type Rendered, render } from "../testing/render";
import { HouseAir } from "./HouseAir";
import { useClimateLoads } from "./useClimateLoads";

const SERIES = (temperature: number[]) => ({
  temperature_c: temperature,
  humidity_pct: temperature.map(() => 85),
  co2_ppm: temperature.map(() => 420),
  removed_kg: temperature.map(() => 0),
  condensed_kg: temperature.map(() => 0),
});
const NO_PROBES = [] as const;
const RUN: ScenarioRun = { scenarioId: "climate_box", time: 120 };

function Probe({ run }: { run: ScenarioRun }) {
  const { houseAir } = useClimateLoads(run, NO_PROBES);
  return <HouseAir state={houseAir} />;
}

/** Answers held until a test lets each come, by the address asked for. */
function heldAnswers() {
  const waiting = new Map<string, (body: unknown) => void>();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      return new Promise<Response>((resolve) => {
        waiting.set(url, (body) => resolve(Response.json(body)));
      });
    }),
  );
  return async (fragment: string, own: boolean, body: unknown) => {
    const found = [...waiting.keys()].find(
      (url) =>
        url.includes(fragment) &&
        url.includes("climate/house") &&
        url.includes("all_off=0") === own,
    );
    expect(found, `a request for ${fragment}`).toBeDefined();
    await act(async () => {
      waiting.get(found as string)?.(body);
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(0);
    });
  };
}

const OWN = true;
const WHOLE = false;
const trace = (times: number[], air: number[], off: number[] | null) => ({
  times_s: times,
  controlled: SERIES(air),
  all_off: off === null ? null : SERIES(off),
});

function airRow(container: HTMLElement): string | null | undefined {
  return container.querySelector('[data-testid="house-air-°C"]')?.textContent;
}

describe("the house's air beside the same run all off", () => {
  let rendered: Rendered;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    rendered.unmount();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  async function runAnsweredWhole(answer: ReturnType<typeof heldAnswers>): Promise<void> {
    rendered = render(<Probe run={RUN} />);
    await answer("t=120", OWN, trace([0, 60, 120], [16, 15.8, 15.6], null));
    await answer("t=120", WHOLE, trace([0, 60, 120], [16, 15.8, 15.6], [16, 15.2, 14.5]));
    expect(airRow(rendered.container)).toBe("Air 15.6 °C, all off 14.5 °C");
  }

  it("keeps it across the run's moments, until the next arrives", async () => {
    const answer = heldAnswers();
    await runAnsweredWhole(answer);

    rendered.rerender(<Probe run={{ ...RUN, time: 180 }} />);
    await answer("t=180", OWN, trace([0, 60, 120, 180], [16, 15.8, 15.6, 15.4], null));

    expect(airRow(rendered.container)).toBe("Air 15.4 °C, all off on its way");
    expect(rendered.container.querySelector(".house-air-off")).not.toBeNull();

    await answer(
      "t=180",
      WHOLE,
      trace([0, 60, 120, 180], [16, 15.8, 15.6, 15.4], [16, 15, 14, 13]),
    );
    expect(airRow(rendered.container)).toBe("Air 15.4 °C, all off 13.0 °C");
  });

  it.each<[string, ScenarioRun, string]>([
    ["scenario", { ...RUN, scenarioId: "tomgro_house" }, "tomgro_house"],
    ["weather", { ...RUN, weather: "cold_spring_day" }, "weather=cold_spring_day"],
    ["layout", { ...RUN, layout: "another" }, "layout=another"],
    ["openings", { ...RUN, openings: { roof_vent: 1 } }, "open=roof_vent:1"],
    ["levels", { ...RUN, levels: { heater: 1 } }, "set=heater:1"],
  ])("draws no other run's beside a run of another %s", async (_what, other, asked) => {
    const answer = heldAnswers();
    await runAnsweredWhole(answer);

    rendered.rerender(<Probe run={other} />);
    await answer(asked, OWN, trace([0, 60, 120], [20, 20.5, 21], null));

    expect(airRow(rendered.container)).toBe("Air 21.0 °C, all off on its way");
    expect(rendered.container.querySelector(".house-air-off")).toBeNull();
  });

  it("draws no new run's beside the last run's own air, if it arrives first", async () => {
    const answer = heldAnswers();
    await runAnsweredWhole(answer);

    rendered.rerender(<Probe run={{ ...RUN, weather: "cold_spring_day" }} />);
    await answer("weather=cold_spring_day", WHOLE, trace([0, 60, 120], [20, 20.5, 21], [9, 8, 7]));

    expect(airRow(rendered.container)).not.toBe("Air 15.6 °C, all off 7.0 °C");
  });
});
