// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { button, click, type Rendered, render, said } from "../testing/render";
import {
  type CropPlantState,
  cropPlantUrl,
  cropUrl,
  loadCropPlant,
  parseCropPlant,
  withCrop,
} from "./crop";
import type { Plant } from "./generated/plantTypes";
import { describeDays, PlantDays } from "./PlantDays";

const PLANT_ID = "reference_greenhouse_plant_001";
// A plant of one phytomer that has borne a fruit and had it picked, as the
// simulator's crop writes it.
const STRUCTURE: Plant = {
  born_tt: 0,
  plant_id: PLANT_ID,
  thermal_time: 900,
  seed: 1,
  traits: {
    vigour: 1,
    phyllochron_scale: 1,
    internode_length_scale: 1,
    stem_diameter_scale: 1,
    leaf_length_scale: 1,
    leaf_insertion_scale: 1,
    leaf_droop_scale: 1,
    rotation_rad: 0,
  },
  laid_internodes: 0,
  stem: {
    born_tt: 0,
    axis_id: `${PLANT_ID}_stem`,
    phytomers: [
      {
        born_tt: 0,
        phytomer_id: `${PLANT_ID}_n01`,
        rank: 1,
        internode: {
          born_tt: 0,
          internode_id: `${PLANT_ID}_n01_internode`,
          length_cm: 5,
          diameter_mm: 8,
          final_length_cm: 6,
          final_diameter_mm: 10,
        },
        leaf: {
          born_tt: 0,
          leaf_id: `${PLANT_ID}_n01_leaf`,
          length_cm: 20,
          final_length_cm: 40,
          stage: "mature",
        },
        truss: null,
      },
    ],
  },
  history: [
    {
      thermal_time: 880,
      action: { kind: "harvest_fruit", fruit_id: `${PLANT_ID}_t01_fr01` },
      applied: true,
      note: `harvested ${PLANT_ID}_t01_fr01, 98 g`,
      organs: [`${PLANT_ID}_t01_fr01`],
      harvested_g: 98,
    },
  ],
};
const DAY = (temperature: number, light: number) => ({
  mean_temperature_c: temperature,
  par_mol_m2_day: light,
  co2_ppm: 420,
  water_status: 1,
});
const BODY = {
  time_s: 2 * DAY_S + 600,
  days: 2,
  structure: STRUCTURE,
  environments: [DAY(13.58, 17.97), DAY(13.62, 18.33)],
};

function entity(entityId: string, properties: SceneEntity["properties"]): SceneEntity {
  return {
    entity_id: entityId,
    kind: "LEAF",
    transform: {
      position: { x: 0, y: 0, z: 0 },
      rotation: { w: 1, x: 0, y: 0, z: 0 },
    },
    shape: { shape: "sphere", radius: 0.01 },
    color: { r: 0, g: 1, b: 0, a: 1 },
    label: null,
    material: null,
    properties,
  } as SceneEntity;
}

describe("a run's crop", () => {
  it("is asked for at the start of the days it has lived, as the climate is", () => {
    const run = { scenarioId: "reference_greenhouse", levels: { heater: 1 } };

    expect(cropUrl({ ...run, time: 2 * DAY_S + 600 })).toBe(
      "/api/scenarios/reference_greenhouse/crop?set=heater:1&t=172800",
    );
    expect(cropUrl({ ...run, time: 3 * DAY_S })).toBe(
      "/api/scenarios/reference_greenhouse/crop?set=heater:1&t=259200",
    );
    expect(cropPlantUrl({ ...run, time: DAY_S - 1 }, PLANT_ID)).toBe(
      `/api/scenarios/reference_greenhouse/crop/${PLANT_ID}?set=heater:1`,
    );
  });

  it("takes the place of every organ the scene draws, on its own day", () => {
    const wall = entity("wall", {});
    const scene = {
      schema_version: 1,
      greenhouse_id: "reference_greenhouse",
      simulated_day: 0,
      entities: [wall, entity("p1_n01_leaf", { organ_id: "p1_n01_leaf", plant_id: "p1" })],
    } as SceneSnapshot;
    const grown = entity("p1_n02_leaf", { organ_id: "p1_n02_leaf", plant_id: "p1" });
    const crop = { ...scene, simulated_day: 3, entities: [grown] };

    expect(withCrop(scene, crop)).toEqual({ ...scene, simulated_day: 3, entities: [wall, grown] });
  });

  it("takes the place of every plant of the simple crop the scene draws whole", () => {
    const wall = entity("wall", {});
    const planted = { ...entity("p1", { age_days: 0 }), kind: "PLANT" } as SceneEntity;
    const scene = {
      schema_version: 1,
      greenhouse_id: "climate_box",
      simulated_day: 0,
      entities: [wall, planted],
    } as SceneSnapshot;
    const grown = { ...entity("p1", { age_days: 3 }), kind: "PLANT" } as SceneEntity;
    const crop = { ...scene, simulated_day: 3, entities: [grown] };

    expect(withCrop(scene, crop)).toEqual({ ...scene, simulated_day: 3, entities: [wall, grown] });
  });

  it("takes the place of every canopy of a crop grown by area the scene draws", () => {
    const wall = entity("wall", {});
    const planted = { ...entity("row_1_canopy", { lai: 0.014 }), kind: "CANOPY" } as SceneEntity;
    const scene = {
      schema_version: 1,
      greenhouse_id: "tomgro_box",
      simulated_day: 0,
      entities: [wall, planted],
    } as SceneSnapshot;
    const grown = { ...entity("row_1_canopy", { lai: 0.75 }), kind: "CANOPY" } as SceneEntity;
    const crop = { ...scene, simulated_day: 3, entities: [grown] };

    // Once, as the crop has it on its day, not twice under one id.
    expect(withCrop(scene, crop)).toEqual({ ...scene, simulated_day: 3, entities: [wall, grown] });
  });
});

describe("a plant's days", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  it("are checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;
    const refused = (async () => new Response("{}", { status: 404 })) as typeof fetch;

    const loaded = await loadCropPlant("/x", answered);
    expect(loaded.status).toBe("loaded");
    const plant = parseCropPlant(BODY);
    expect(plant.plantId).toBe(PLANT_ID);
    expect(plant.environments).toEqual([
      { temperature: 13.58, light: 17.97, co2: 420, water: 1 },
      { temperature: 13.62, light: 18.33, co2: 420, water: 1 },
    ]);
    expect(plant.history).toEqual([
      { thermalTime: 880, applied: true, note: `harvested ${PLANT_ID}_t01_fr01, 98 g` },
    ]);
    expect(await loadCropPlant("/x", refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 404",
    });
    expect(() => parseCropPlant({ ...BODY, days: 3 })).toThrow("not what the viewer expects");
  });

  it("are written as the last day's and their range", () => {
    expect(describeDays([17.97, 18.33, 18.1], "Light", "mol/m²/d", 1)).toBe(
      "Light 18.1 mol/m²/d on day 2, 18.0 to 18.3",
    );
  });

  it("chart each quantity day by day, list what was picked, and select an organ", () => {
    const onSelect = vi.fn();
    const state: CropPlantState = { status: "loaded", plant: parseCropPlant(BODY) };
    shown = render(<PlantDays state={state} selectedOrgan={null} onSelect={onSelect} />);

    expect(said(shown.container, "plant-days-air")).toBe("Air 13.6 °C on day 1, 13.6 to 13.6");
    expect(said(shown.container, "plant-days-light")).toBe(
      "Light 18.3 mol/m²/d on day 1, 18.0 to 18.3",
    );
    expect(said(shown.container, "plant-days-co2")).toBe("CO₂ 420 ppm on day 1, 420 to 420");
    expect(said(shown.container, "plant-event")).toBe(
      `at 880 °Cd: harvested ${PLANT_ID}_t01_fr01, 98 g`,
    );
    click(button(shown.container, `${PLANT_ID}_n01_leaf`));
    expect(onSelect).toHaveBeenCalledWith(`${PLANT_ID}_n01_leaf`);
  });

  it("say so before the first day ends, while they grow, and when they cannot", () => {
    const ignore = () => undefined;
    const young: CropPlantState = {
      status: "loaded",
      plant: parseCropPlant({ ...BODY, days: 0, environments: [] }),
    };
    shown = render(<PlantDays state={young} selectedOrgan={null} onSelect={ignore} />);
    expect(said(shown.container, "plant-days")).toContain("No day lived yet");

    shown.rerender(
      <PlantDays state={{ status: "loading" }} selectedOrgan={null} onSelect={ignore} />,
    );
    expect(said(shown.container, "plant-days")).toBe("Growing the plant's days…");
    shown.rerender(
      <PlantDays
        state={{ status: "unavailable", reason: "no plant" }}
        selectedOrgan={null}
        onSelect={ignore}
      />,
    );
    expect(said(shown.container, "plant-days")).toBe(
      "The plant's days are not available: no plant.",
    );
    shown.rerender(<PlantDays state={{ status: "none" }} selectedOrgan={null} onSelect={ignore} />);
    expect(shown.container.textContent).toBe("");
  });
});
