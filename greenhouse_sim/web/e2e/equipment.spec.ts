import { expect, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

// The climate box seen from outside its right side wall, through the glass:
// the heater in its back right corner, and the dehumidifier halfway along its
// left wall, above the plants. A point on each one's side facing the camera.
const ACROSS: CameraPose = {
  position: { x: 6, y: -8, z: 4 },
  target: { x: 6, y: 3.2, z: 1.2 },
};
const HEATER_SIDE = { x: 11.2, y: 0.3, z: 0.6 };
const DEHUMIDIFIER_FRONT = { x: 6.0, y: 5.6, z: 1.3 };
// The fan, high over the front path, seen from inside the house, its face in
// the middle of the view.
const FAN_FACE = { x: 1.15, y: 3.2, z: 2.8 };
const AT_THE_FAN: CameraPose = { position: { x: 5, y: 1.5, z: 3.2 }, target: FAN_FACE };

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

test("equipment: a device is picked, switched on, set to a level and off, and the scene says so", async ({
  page,
}) => {
  const status = page.getByTestId("scene-status");
  const equipment = page.getByRole("group", { name: "Equipment" });
  const heater = page.getByTestId("equipment-heater");
  const level = page.getByTestId("property-level");

  await test.step("each piece is drawn where it stands, as what it is, off", async () => {
    await page.goto(`/?scenario=climate_box&camera=${cameraText(AT_THE_FAN)}`);
    await expect(status).toContainText("climate_box, day 0, 114 entities");
    await expect(page.getByTestId("equipment-fan")).toHaveText("off");
    await selectAt(page, FAN_FACE, "climate_box_fan", AT_THE_FAN);
    await expect(page.getByTestId("selected-type")).toHaveText("fan");
    await expect(page.getByTestId("property-flow_m3_s")).toHaveText("1");

    await page.goto(`/?scenario=climate_box&camera=${cameraText(ACROSS)}`);
    await expect(status).toContainText("climate_box, day 0, 114 entities");
    await expect(page.getByTestId("equipment-dehumidifier")).toHaveText("off");
    await selectAt(page, DEHUMIDIFIER_FRONT, "climate_box_dehumidifier", ACROSS);
    await expect(page.getByTestId("selected-type")).toHaveText("dehumidifier");
    await expect(page.getByTestId("property-removal_kg_h")).toHaveText("5");
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
    await expect(page.getByTestId("selected-type")).toHaveText("heater");
    await expect(page.getByTestId("property-power_w")).toHaveText("10000");
    await expect(heater).toHaveText("off");
    await expect(level).toHaveText("0");
  });

  await test.step("switched on, it runs at full power, and the address keeps it", async () => {
    await equipment.getByRole("checkbox", { name: "heater" }).check();
    await expect(heater).toHaveText("100%, 10 kW");
    await expect(page).toHaveURL(/&set=heater:1(&|$)/);
    await expect(level).toHaveText("1");
  });

  await test.step("its slider sets its level", async () => {
    await equipment.getByRole("slider", { name: "heater level" }).fill("50");
    await expect(heater).toHaveText("50%, 5 kW");
    await expect(page).toHaveURL(/&set=heater:0.5(&|$)/);
    await expect(level).toHaveText("0.50");
  });

  await test.step("switched off, it does nothing", async () => {
    await equipment.getByRole("checkbox", { name: "heater" }).uncheck();
    await expect(heater).toHaveText("off");
    await expect(page).toHaveURL(/&set=heater:0(&|$)/);
    await expect(level).toHaveText("0");
  });

  await test.step("the address alone sets the levels it names", async () => {
    await page.goto("/?scenario=climate_box&set=fan:1,dehumidifier:0.25");
    await expect(page.getByTestId("equipment-fan")).toHaveText("100%, 1 m³/s");
    await expect(page.getByTestId("equipment-dehumidifier")).toHaveText("25%, 1.25 kg/h");
    await expect(heater).toHaveText("off");
  });
});
