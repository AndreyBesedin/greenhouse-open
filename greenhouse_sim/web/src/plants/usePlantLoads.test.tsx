// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ScenarioRun } from "../scene/run";
import { recordingFetch } from "../testing/recordingFetch";
import { renderHook } from "../testing/renderHook";
import { usePlantLoads } from "./usePlantLoads";

const RUN: ScenarioRun = { scenarioId: "reference_greenhouse", time: 129_600 };
const PLANT = "reference_greenhouse_plant_001";

type Props = Parameters<typeof usePlantLoads>[0];

const NOTHING_SELECTED: Props = {
  run: RUN,
  climate: RUN,
  organCrop: true,
  selectedPlant: null,
  qaMode: false,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("usePlantLoads", () => {
  it("asks for nothing while no plant is selected, out of QA mode", () => {
    const asked = recordingFetch();
    renderHook(usePlantLoads, NOTHING_SELECTED);

    expect(asked).toEqual([]);
  });

  it("asks for the plants' light in a climate run, and the plant's days in an organ crop", () => {
    const asked = recordingFetch();
    renderHook(usePlantLoads, { ...NOTHING_SELECTED, selectedPlant: PLANT });

    expect(asked).toHaveLength(2);
    expect(asked[0]).toBe("/api/scenarios/reference_greenhouse/climate/plants?t=129600");
    expect(asked[1]).toBe(`/api/scenarios/reference_greenhouse/crop/${PLANT}?t=86400`);
  });

  it("asks for the light in QA mode, which labels every plant, and no days without a plant", () => {
    const asked = recordingFetch();
    renderHook(usePlantLoads, { ...NOTHING_SELECTED, qaMode: true });

    expect(asked).toEqual(["/api/scenarios/reference_greenhouse/climate/plants?t=129600"]);
  });

  it("asks for no light outside a climate run, nor days of a simple crop", () => {
    const asked = recordingFetch();
    renderHook(usePlantLoads, {
      ...NOTHING_SELECTED,
      climate: null,
      organCrop: false,
      selectedPlant: PLANT,
    });

    expect(asked).toEqual([]);
  });
});
