// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SceneEntity } from "../scene/generated/snapshotTypes";
import type { ScenarioRun } from "../scene/run";
import { recordingFetch } from "../testing/recordingFetch";
import { renderHook } from "../testing/renderHook";
import { useSensorReadings } from "./useSensorReadings";

const RUN: ScenarioRun = { scenarioId: "reference_greenhouse", time: 3600 };
const RUNNING: ScenarioRun = { ...RUN, levels: { fan_right: 1 } };

function entity(kind: string): SceneEntity {
  return { entity_id: `reference_greenhouse_${kind}`, kind } as SceneEntity;
}

type Props = { selected: SceneEntity | null; run: ScenarioRun | null; qaMode: boolean };

function useReadings({ selected, run, qaMode }: Props) {
  return useSensorReadings(selected, run, qaMode);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSensorReadings", () => {
  it("asks for nothing until a sensor or a camera is selected", () => {
    const asked = recordingFetch();
    renderHook(useReadings, { selected: entity("PLANT"), run: RUN, qaMode: false });

    expect(asked).toEqual([]);
  });

  it("asks for the run's observations, and the all-off run's only when something runs", () => {
    const asked = recordingFetch();
    const hook = renderHook(useReadings, { selected: entity("SENSOR"), run: RUN, qaMode: false });

    expect(asked).toEqual(["/api/scenarios/reference_greenhouse/climate/observations?t=3600"]);
    hook.rerender({ selected: entity("CAMERA"), run: RUNNING, qaMode: false });
    expect(asked.slice(1)).toEqual([
      "/api/scenarios/reference_greenhouse/climate/observations?set=fan_right:1&t=3600",
      // All off: no levels, no commands, not even the scenario's daily ones.
      "/api/scenarios/reference_greenhouse/climate/observations?daily=none&t=3600",
    ]);
  });

  it("asks for the truth in QA mode only, and for clean sensors' if asked", () => {
    const asked = recordingFetch();
    const hook = renderHook(useReadings, { selected: entity("SENSOR"), run: RUN, qaMode: true });

    expect(asked).toEqual([
      "/api/scenarios/reference_greenhouse/climate/observations?t=3600",
      "/api/scenarios/reference_greenhouse/climate/truth?t=3600",
    ]);
    act(() => hook.current.setImperfect(false));
    expect(hook.current.imperfect).toBe(false);
    expect(asked.slice(2)).toEqual([
      "/api/scenarios/reference_greenhouse/climate/observations?t=3600&clean=1",
      "/api/scenarios/reference_greenhouse/climate/truth?t=3600",
    ]);
  });
});
