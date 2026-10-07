import { expect, test } from "@playwright/test";

test("a scenario's air field is chosen, loaded and drawn over its scene", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001");
  await expect(page.getByTestId("field-status")).toHaveText("No field drawn.");

  await page.getByRole("combobox", { name: "Air field" }).selectOption("shear");

  await expect(page).toHaveURL(/\?scenario=gh_001&field=shear$/);
  // gh_001's air under its gutters, 16 by 9.6 m and 3.5 m high, in cells of
  // at most 0.5 m; still at the floor, 0.25 (m/s)/m faster with height.
  await expect(page.getByTestId("field-status")).toHaveText(
    "gh_001_shear (synthetic:shear): 16 × 20 × 7 cells, air speed 0.06 to 0.81 m/s.",
  );

  await page.getByRole("combobox", { name: "Air field" }).selectOption("none");
  await expect(page).toHaveURL(/\?scenario=gh_001$/);
  await expect(page.getByTestId("field-status")).toHaveText("No field drawn.");
});
