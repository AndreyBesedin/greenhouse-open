import { expect, test } from "@playwright/test";

import { QA_GREENHOUSE_PATH, QA_GREENHOUSE_VIEWS } from "../src/qa/greenhouseViews.ts";
import { QA_LAYOUT_PATH, QA_LAYOUT_VIEWS } from "../src/qa/layoutViews.ts";
import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../src/qa/qaPage.ts";

// The screenshot comparison itself runs only in CI's container
// (e2e/visual). This checks the page works wherever the viewer runs.
test("the renderer's QA page draws its seeded scene, without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });

  await page.goto(`${QA_RENDERER_PATH}?seed=${DEFAULT_QA_SEED}`);

  await expect(page.getByTestId("qa-caption")).toHaveText(`Renderer QA, seed ${DEFAULT_QA_SEED}`);
  await expect(page.getByTestId("debug-label")).toHaveText(QA_SELECTED_ID);
  await expect(page.getByTestId("legend-property")).toHaveText("height_cm");
  await expect(page.getByTestId("legend-min")).toHaveText("21.80");
  await expect(page.getByTestId("legend-max")).toHaveText("99.57");
  expect(errors).toEqual([]);
});

test("a QA address without a whole-number seed says so", async ({ page }) => {
  await page.goto(`${QA_RENDERER_PATH}?seed=abc`);

  await expect(page.getByRole("alert")).toHaveText(
    "The seed must be a whole number, such as ?seed=42.",
  );
});

test("the QA greenhouse draws each of its views, without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });

  for (const view of QA_GREENHOUSE_VIEWS) {
    await page.goto(`${QA_GREENHOUSE_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toHaveText(`Greenhouse QA, ${view} view`);
  }
  await expect(page.getByTestId("category")).toHaveCount(7);
  expect(errors).toEqual([]);

  await page.goto(`${QA_GREENHOUSE_PATH}?view=sideways`);
  await expect(page.getByRole("alert")).toHaveText(
    "The view must be outside, aisle, top or section.",
  );
});

test("the QA layout draws each of its views, without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });

  for (const view of QA_LAYOUT_VIEWS) {
    await page.goto(`${QA_LAYOUT_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toHaveText(`Layout QA, ${view} view`);
  }
  expect(errors).toEqual([]);

  // Only the plan is coloured by category, with its legends.
  await page.goto(`${QA_LAYOUT_PATH}?view=top`);
  await expect(page.getByTestId("layout-category")).toHaveText([
    "planting position",
    "crop gutter",
    "slab",
    "walkway",
    "service zone",
    "keep-out",
    "rail",
    "pipe",
    "wire",
    "obstacle",
  ]);
  await page.goto(`${QA_LAYOUT_PATH}?view=between-rows`);
  await expect(page.getByTestId("qa-caption")).toHaveText("Layout QA, between-rows view");
  await expect(page.getByTestId("layout-category")).toHaveCount(0);

  await page.goto(`${QA_LAYOUT_PATH}?view=sideways`);
  await expect(page.getByRole("alert")).toHaveText(
    `The view must be ${QA_LAYOUT_VIEWS.join(" or ")}.`,
  );
});
