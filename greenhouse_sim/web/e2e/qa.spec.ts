import { expect, test } from "@playwright/test";

import { QA_GREENHOUSE_PATH, QA_GREENHOUSE_VIEWS } from "../src/qa/greenhouseViews.ts";
import { QA_LAYOUT_PATH, QA_LAYOUT_VIEWS } from "../src/qa/layoutViews.ts";
import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../src/qa/qaPage.ts";
import { QA_REFERENCE_PATH, QA_REFERENCE_VIEWS } from "../src/qa/referencePage.ts";

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

test("the reference greenhouse's QA page draws each golden view and its probes", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  const probes: Record<string, string> = {};
  for (const view of QA_REFERENCE_VIEWS) {
    await page.goto(`${QA_REFERENCE_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toContainText(
      `Reference greenhouse, ${view} view: `,
      { timeout: 30_000 },
    );
    probes[view] = (await page.getByTestId("qa-probes").textContent()) ?? "";
  }
  expect(errors).toEqual([]);

  // The opening day's sun, low at dawn and evening, high at its noon.
  expect(probes.dawn).toContain("sun 10.84° up");
  expect(probes.noon).toContain("sun 59.19° up");
  expect(probes.evening).toContain("sun 9.24° up");
  // The fans' jet, and nothing where they are off; the house as one volume
  // does not feel them.
  expect(probes["fans-on"]).toContain("house air 28.14 °C, sun 59.19° up, jet 1.39 m/s");
  expect(probes["fans-off"]).toContain("house air 28.14 °C, sun 59.19° up, jet 0 m/s");
  // Shut at noon, the vents exchange nothing, and the house is 10 °C warmer.
  expect(probes["vents-open"]).toContain("vents exchange 1.08 m³/s");
  expect(probes["vents-closed"]).toContain("house air 38.12 °C");
  expect(probes["vents-closed"]).toContain("vents exchange 0 m³/s");
  // A young crop bears no fruit; on the opening day, the first is red.
  expect(probes.young).toContain("4257 leaves, 0 fruits, 0 red");
  expect(probes.fruiting).toContain("10373 leaves, 741 fruits, 1 red");

  await page.goto(`${QA_REFERENCE_PATH}?view=sideways`);
  await expect(page.getByRole("alert")).toHaveText(
    "There is no such view of the reference greenhouse.",
  );
});
