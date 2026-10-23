// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ScenarioSummary } from "../scenarios";
import { recordingFetch } from "../testing/recordingFetch";
import { renderHook } from "../testing/renderHook";
import { type ScenarioRun, scenarioRun } from "./run";
import type { SceneSource } from "./source";
import { useSceneLoads } from "./useSceneLoads";

const DAY_S = 86_400;
const SUMMARY: ScenarioSummary = {
  id: "reference_greenhouse",
  name: "Reference greenhouse",
  description: "",
  plants: 32,
  duration_days: 120,
  crop_model: "organ",
  layouts: ["default"],
  thermostat: "heater",
};

type Props = { source: SceneSource; summary: ScenarioSummary | undefined; run: ScenarioRun | null };

function useLoads({ source, summary, run }: Props) {
  return useSceneLoads(source, summary, run);
}

function scenarioAt(time: number): Props {
  const source: SceneSource = { kind: "scenario", scenarioId: "reference_greenhouse", time };
  return {
    source,
    summary: SUMMARY,
    run: scenarioRun(source as Extract<SceneSource, { kind: "scenario" }>),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSceneLoads", () => {
  it("asks for the run's equipment when a thermostat runs its heater, and no crop on its first day", () => {
    const asked = recordingFetch();
    const hook = renderHook(useLoads, scenarioAt(DAY_S / 2));

    expect(asked.filter((url) => url.includes("/equipment") || url.includes("/crop"))).toEqual([
      "/api/scenarios/reference_greenhouse/climate/equipment?t=43200",
    ]);
    expect(hook.current.organCrop).toBe(true);
    expect(hook.current.cropProgress.latest.status).toBe("none");
  });

  it("asks for the crop of an organ crop once a day has ended", () => {
    const asked = recordingFetch();
    renderHook(useLoads, scenarioAt(DAY_S + DAY_S / 2));

    expect(asked.filter((url) => url.includes("/crop"))).toHaveLength(1);
  });

  it("asks for no equipment without a thermostat, nor a crop of a simple crop", () => {
    const asked = recordingFetch();
    const props = scenarioAt(DAY_S + DAY_S / 2);
    renderHook(useLoads, {
      ...props,
      summary: { ...SUMMARY, thermostat: null, crop_model: "simple" },
    });

    expect(asked.some((url) => url.includes("/equipment") || url.includes("/crop"))).toBe(false);
  });
});
