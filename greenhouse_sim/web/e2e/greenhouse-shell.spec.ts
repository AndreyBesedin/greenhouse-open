import { expect, test } from "@playwright/test";

import { QA_GREENHOUSE_PATH } from "../src/qa/greenhouseViews.ts";

/**
 * P01's final QA, `greenhouse-shell`, in the browser: change a scenario's
 * greenhouse through the address bar, and check what the viewer draws. The
 * geometry itself is checked over many greenhouses by the simulator's
 * tests/test_greenhouse_shell.py; the screenshots by the visual checks job.
 */

// The climate box made three of its 6.4 m spans wide, in four bays.
const SHELL = "envelope=bays:4,eave_height:4,length:12,ridge_height:4.8,spans:3,width:19.2";

test("greenhouse-shell: a changed greenhouse is drawn to its dimensions, open and labelled", async ({
  page,
}) => {
  await test.step("the greenhouse is changed through the address bar", async () => {
    await page.goto(`/?scenario=climate_box&${SHELL}`);
    // Three spans and four bays: 6 roof slopes, 5 frames of 4 posts and 6 rafters.
    await expect(page.getByTestId("scene-status")).toContainText(
      "climate_box, day 0, 168 entities",
    );
  });

  await test.step("its physical dimensions are the ones asked for", async () => {
    await page.getByLabel("Dimensions and axis labels").check();
    await expect(page.getByTestId("debug-label")).toHaveText([
      "x",
      "y",
      "z",
      "length 12.00 m",
      "width 19.20 m",
      "height 4.80 m",
    ]);
    await page.getByLabel("Dimensions and axis labels").uncheck();
  });

  await test.step("a vent opens, and the address keeps both changes", async () => {
    await page.getByRole("group", { name: "Openings" }).getByRole("slider").first().fill("100");
    // Wide open, at 45°, the 4 by 1 m vent's curtain.
    await expect(page.getByTestId("opening-roof_vent")).toHaveText("100%, 3.77 m²");
    await expect(page).toHaveURL(new RegExp(`\\?scenario=climate_box&${SHELL}&open=roof_vent:1$`));
  });

  await test.step("the debug colours follow each surface's semantics", async () => {
    await page.getByRole("checkbox", { name: "Categories" }).check();
    await expect(page.getByTestId("category")).toHaveText([
      "floor",
      "wall",
      "roof",
      "vent",
      "door",
      "gutter",
      "frame",
    ]);
  });

  await test.step("a greenhouse that cannot stand is refused, with the reason", async () => {
    await page.goto("/?scenario=climate_box&envelope=ridge_height:2");
    await expect(page.getByTestId("scene-status")).toContainText(
      "the ridge (2.0 m) is below the eaves (4.0 m)",
    );
  });

  await test.step("the camera can enter the greenhouse", async () => {
    await page.goto(`${QA_GREENHOUSE_PATH}?view=aisle`);
    await expect(page.getByTestId("qa-caption")).toHaveText("Greenhouse QA, aisle view");
  });
});
