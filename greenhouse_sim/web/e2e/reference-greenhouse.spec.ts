import { expect, test } from "@playwright/test";
import { chooser } from "./chooser";
import { unfold } from "./folds";

// The reference scenario (P09.1): one manifest boots the whole greenhouse,
// its 32 plants, organ by organ (P09.3), its equipment, its heater on a
// thermostat (P10.3), its vents and door, its sensors and its camera; and
// the viewer lists it first.
test("reference greenhouse: its manifest boots the whole scene, and it is listed first", async ({
  page,
}) => {
  await page.goto("/");
  const firstRow = (await chooser(page))
    .getByRole("table", { name: "Scenarios" })
    .locator("tbody tr")
    .first();
  await expect(firstRow.locator(".scenario-name")).toHaveText("Reference greenhouse");
  await expect(firstRow.getByRole("button", { name: "Open reference_greenhouse" })).toBeVisible();
  await expect(firstRow).toContainText("32");
  await expect(firstRow).toContainText("120");

  await page.goto("/?scenario=reference_greenhouse");
  await expect(page.getByTestId("scene-status")).toContainText(
    "reference_greenhouse, day 0, 3108 entities",
  );
  for (const device of ["fan_right", "fan_left", "dehumidifier"]) {
    await expect(page.getByTestId(`equipment-${device}`)).toHaveText("off");
  }
  // Its thermostat runs its heater by the air (P10.3): the house starts at
  // 14 °C on a March night, under the night's 16 °C. The scene draws it so
  // once the run has said so.
  await expect(page.getByTestId("equipment-heater")).toHaveText(
    "100%, 30 kW, by its thermostat at 16 °C",
    { timeout: 60_000 },
  );
  for (const vent of ["roof_vent_1", "roof_vent_2", "roof_vent_3"]) {
    await expect(page.getByTestId(`opening-${vent}`)).toHaveText(/^0%, /);
  }

  await unfold(page, "Display");
  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("sensor-category")).toHaveText(["sensor", "camera"]);
});

// Its thermostat's heater is the run's to say (P10.3): when the simulator
// cannot say it, the viewer says so, rather than drawing it off unsaid.
test("reference greenhouse: a heater the run cannot say is reported, not drawn off unsaid", async ({
  page,
}) => {
  await page.route("**/api/scenarios/reference_greenhouse/climate/equipment*", (failing) =>
    failing.fulfill({ status: 500, json: { error: "a failure for the test" } }),
  );
  await page.goto("/?scenario=reference_greenhouse");
  await expect(page.getByTestId("scene-status")).toContainText("reference_greenhouse, day 0");
  await expect(page.getByTestId("scene-failures")).toHaveText(
    "Not drawn as asked: the equipment is not available (the simulator API answered 500).",
    { timeout: 60_000 },
  );
});
