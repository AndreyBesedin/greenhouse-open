import { expect, test } from "@playwright/test";
import { unfold } from "./folds";

// The TOMGRO house's rows grow Reduced-State TOMGRO by area, which has no
// plants: its crop is charted through the run's days, not drawn (decision
// 0083).
const DAY_S = 86_400;
const NOON_S = 43_200;
// A later day's moment takes the simulator the house's air, and the light
// above each row, through the days before it.
const ARRIVES = { timeout: 90_000 };

test("crop by area: the TOMGRO house's rows are charted day by day, labelled as predictions", async ({
  page,
}) => {
  test.setTimeout(240_000);
  const summary = page.getByTestId("area-crop-summary");
  const course = page.getByRole("figure", { name: "Crop by area" });

  await test.step("on its fourth day, the course of its first three", async () => {
    await page.goto(`/?scenario=tomgro_house&field=climate&t=${3 * DAY_S + NOON_S}`);
    await expect(page.getByTestId("scene-status")).toContainText(
      "tomgro_house, 3 days in",
      ARRIVES,
    );
    await unfold(page, "Crop by area");
    await expect(summary).toHaveText(
      /^Crop by area after 3 days: leaf area index \d\.\d+ m² m⁻²$/,
      ARRIVES,
    );
    // Each of its model's five states, the house's line over its rows'.
    await expect(course.getByRole("img")).toHaveCount(5);
    await expect(course.getByRole("img").first()).toHaveAccessibleName(
      "The house's main stem nodes after each day, in nodes, its rows' least to most behind it",
    );
    await expect(course).toContainText(
      "After 3 days, by Reduced-State TOMGRO: the model's predictions, per m² of floor",
    );
    await expect(page.getByTestId("area-crop-lai")).toHaveText(
      /^Leaf area index \d\.\d+ m² m⁻², rows /,
    );
  });

  await test.step("a day on, a day more", async () => {
    await page
      .getByRole("group", { name: "Climate run" })
      .getByRole("button", { name: "Next day" })
      .click();
    await expect(summary).toHaveText(/^Crop by area after 4 days: /, ARRIVES);
    await expect(course.getByRole("img")).toHaveCount(5);
  });
});
