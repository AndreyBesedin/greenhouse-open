import { expect, test } from "@playwright/test";

import { DRAWN_TIMEOUT_MS, objectCount, settledObjectCount } from "./hud";

// The climate box's air, small enough to draw quickly in software, with a
// probe in it. Its front camera's view is outlined by eight lines.
const PROBED_AIR = "/?scenario=climate_box&field=shear&probes=3:3.2:0.75";
const CAMERA_VIEW_LINES = 8;

test("overlays over the scene are hidden and shown again without asking the simulator", async ({
  page,
}) => {
  await page.goto(PROBED_AIR);
  const status = page.getByTestId("field-status");
  await expect(status).toContainText("24 × 13 × 8 cells");
  await expect(page.getByTestId("debug-label")).toHaveText(["P1"]);
  const fieldStatus = await status.textContent();
  const reading = await page.getByTestId("probe-1-reading").textContent();
  const drawn = await settledObjectCount(page);
  const asked: string[] = [];
  page.on("request", (request) => asked.push(request.url()));
  const shown = page.getByRole("group", { name: "Shown in the view" });
  const switches = ["Air field arrows", "Camera views", "Probes"];

  // The field's arrows, one batch of them, leave the view with their legend,
  // and the field stays loaded.
  await shown.getByRole("checkbox", { name: "Air field arrows" }).uncheck();
  await expect(page.getByRole("figure", { name: "Field legend" })).toHaveCount(0);
  await expect.poll(() => objectCount(page), { timeout: DRAWN_TIMEOUT_MS }).toBe(drawn - 1);
  await expect(status).toHaveText(fieldStatus ?? "");
  await shown.getByRole("checkbox", { name: "Camera views" }).uncheck();
  await expect
    .poll(() => objectCount(page), { timeout: DRAWN_TIMEOUT_MS })
    .toBe(drawn - 1 - CAMERA_VIEW_LINES);
  // The probe's marks leave it too; the probe still reads the field.
  await shown.getByRole("checkbox", { name: "Probes" }).uncheck();
  await expect(page.getByTestId("debug-label")).toHaveCount(0);
  await expect(page.getByTestId("probe-1-reading")).toHaveText(reading ?? "");

  // Shown again, each is drawn as it was, from what the viewer already holds.
  for (const name of switches) {
    await shown.getByRole("checkbox", { name }).check();
  }
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("air speed (m/s)");
  await expect(page.getByTestId("debug-label")).toHaveText(["P1"]);
  await expect.poll(() => objectCount(page), { timeout: DRAWN_TIMEOUT_MS }).toBe(drawn);

  expect(asked).toEqual([]);
  await expect(page).toHaveURL(/\?scenario=climate_box&field=shear&probes=3:3\.2:0\.75$/);
});

test("a climate run's air is hidden without ending the run or moving its moment", async ({
  page,
}) => {
  await page.goto("/?scenario=climate_box&field=climate&t=600");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 60_000 });
  const houseAir = page.getByRole("figure", { name: "House air" }).getByTestId("house-air-°C");
  await expect(houseAir).toHaveText(/^Air [\d.]+ °C, all off [\d.]+ °C$/);
  const air = await houseAir.textContent();
  const asked: string[] = [];
  page.on("request", (request) => asked.push(request.url()));
  const airField = page
    .getByRole("group", { name: "Shown in the view" })
    .getByRole("checkbox", { name: "Air field arrows" });

  // Choosing no field would end the climate run; hiding its air leaves the
  // run as it stands, its equipment and its charts with it.
  await airField.uncheck();
  await expect(page.getByRole("figure", { name: "Field legend" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Air field" })).toHaveValue("climate");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min");
  await expect(houseAir).toHaveText(air ?? "");
  await airField.check();
  await expect(page.getByRole("figure", { name: "Field legend" })).toBeVisible();

  expect(asked).toEqual([]);
  await expect(page).toHaveURL(/\?scenario=climate_box&field=climate&t=600$/);
});

test("What am I seeing? explains what is drawn, and follows the switches (#205)", async ({
  page,
}) => {
  await page.goto(PROBED_AIR);
  await expect(page.getByTestId("field-status")).toContainText("24 × 13 × 8 cells");
  const card = page.getByRole("region", { name: "What am I seeing?" });
  await expect(card).toHaveCount(0);

  await page.getByRole("button", { name: "What am I seeing?" }).click();
  await expect(card.getByTestId("seen-airField")).toContainText("Air field arrows");
  await expect(card.getByTestId("seen-airField")).toContainText("air speed (m/s)");
  await expect(card.getByTestId("seen-probes")).toContainText("Where the drawn field is read");
  await expect(card.getByTestId("seen-cameraViews")).toBeVisible();
  await expect(card.getByTestId("seen-glass")).toContainText("drawn see-through");
  await expect(card.getByTestId("seen-hidden")).toHaveCount(0);

  // Hidden by its switch, an overlay leaves the card, which says it is hidden.
  const shown = page.getByRole("group", { name: "Shown in the view" });
  await shown.getByRole("checkbox", { name: "Probes" }).uncheck();
  await expect(card.getByTestId("seen-probes")).toHaveCount(0);
  await expect(card.getByTestId("seen-hidden")).toHaveText("Hidden: probes.");

  // Closed, its button stays, to open it again.
  await card.getByRole("button", { name: "Close what am I seeing" }).click();
  await expect(card).toHaveCount(0);
  await expect(page.getByRole("button", { name: "What am I seeing?" })).toBeVisible();
});
