import { expect, test } from "@playwright/test";

test("a scenario's air field is chosen, loaded and drawn over its scene", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001");
  await expect(page.getByTestId("field-status")).toHaveText("No field drawn.");

  await page.getByRole("combobox", { name: "Air field" }).selectOption("shear");

  await expect(page).toHaveURL(/\?scenario=gh_001&field=shear$/);
  // gh_001's air under its gutters, 8 by 9.6 m and 3.5 m high, in cells of
  // at most 0.5 m; still at the floor, 0.25 (m/s)/m faster with height.
  await expect(page.getByTestId("field-status")).toHaveText(
    "gh_001_shear (synthetic:shear): 16 × 20 × 7 cells, air speed 0.06 to 0.81 m/s.",
  );

  await page.getByRole("combobox", { name: "Air field" }).selectOption("none");
  await expect(page).toHaveURL(/\?scenario=gh_001$/);
  await expect(page.getByTestId("field-status")).toHaveText("No field drawn.");
});

test("a field is drawn as arrows, streamlines or a slice, with a legend to match", async ({
  page,
}) => {
  await page.goto("/?scenario=gh_001&field=shear");
  await expect(page.getByTestId("field-status")).toContainText("16 × 20 × 7 cells");
  await expect(page.getByRole("radio", { name: "arrows" })).toBeChecked();
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("air speed (m/s)");

  await page.getByRole("radio", { name: "streamlines" }).check();
  await expect(page).toHaveURL(/&field=shear&fieldView=streamlines$/);

  // A slice across the field's middle height, of its temperature, by default:
  // gh_001's air is 3.5 m high.
  await page.getByRole("radio", { name: "slice" }).check();
  await expect(page).toHaveURL(/&fieldView=slice&slice=temperature:z:1\.75$/);
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("temperature (°C)");
  await expect(page.getByTestId("field-slice-position")).toHaveText("z = 1.75 m");

  await page.getByRole("combobox", { name: "square to" }).selectOption("x");
  await expect(page).toHaveURL(/&slice=temperature:x:4$/);
  await page.getByRole("combobox", { name: "Slice of" }).selectOption("speed");
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("air speed (m/s)");

  // The colours' range can be changed, and given back.
  await page.getByRole("spinbutton", { name: "Lowest colour" }).fill("0.4");
  await expect(page.getByRole("spinbutton", { name: "Lowest colour" })).toHaveValue("0.40");
  await page.getByRole("button", { name: "The field's own range" }).click();
  await expect(page.getByRole("spinbutton", { name: "Lowest colour" })).toHaveValue("0.06");
});

test("the prescribed airflow patterns switch at once, the scenario's own first", async ({
  page,
}) => {
  await page.goto("/?scenario=gh_001");
  const fieldChoice = page.getByRole("combobox", { name: "Air field" });
  await expect(fieldChoice.locator("option")).toHaveText([
    "none",
    "vortex, the scenario's airflow",
    "uniform",
    "buoyancy",
    "shear",
  ]);

  for (const pattern of ["vortex", "uniform", "buoyancy"]) {
    await fieldChoice.selectOption(pattern);
    await expect(page.getByTestId("field-status")).toContainText(
      `gh_001_${pattern} (prescribed:${pattern}): 16 × 20 × 7 cells`,
    );
  }
});
