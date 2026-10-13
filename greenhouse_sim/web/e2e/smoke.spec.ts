import { expect, type Page, test } from "@playwright/test";

/** Everything the page reports as an error, so a test can insist on none. */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  return errors;
}

test("the viewer lists the simulator's scenarios, without console errors", async ({ page }) => {
  const errors = collectErrors(page);

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "greenhouse-sim viewer" })).toBeVisible();
  const scenarios = page.getByRole("table", { name: "Scenarios" });
  for (const scenario of ["Tomato compartment", "Climate box", "Airflow QA Box"]) {
    await expect(scenarios).toContainText(scenario);
  }
  expect(errors).toEqual([]);
});

test("the HUD says how long the simulator took to answer the latest request", async ({ page }) => {
  await page.goto("/?scenario=climate_box");
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0");

  // As the API's Server-Timing header says it, through the preview's proxy.
  await expect(page.getByTestId("simulator-time")).toHaveText(
    /^\d[\d,]* ms for (scenarios|version|health)/,
  );
});

test("the 3D view fills the window and follows its size", async ({ page }) => {
  const errors = collectErrors(page);
  await page.setViewportSize({ width: 1000, height: 700 });

  await page.goto("/");
  const view = page.locator("canvas");
  await expect(view).toBeVisible();
  await expect.poll(() => view.boundingBox()).toMatchObject({ width: 1000, height: 700 });

  await page.setViewportSize({ width: 640, height: 480 });
  await expect.poll(() => view.boundingBox()).toMatchObject({ width: 640, height: 480 });
  expect(errors).toEqual([]);
});
