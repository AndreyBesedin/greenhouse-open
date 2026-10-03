import { expect, test } from "@playwright/test";

test("the viewer lists the simulator's scenarios, without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "greenhouse-sim viewer" })).toBeVisible();
  const scenarios = page.getByRole("table", { name: "Scenarios" });
  for (const scenario of ["gh_001", "gh_002", "gh_demo"]) {
    await expect(scenarios).toContainText(scenario);
  }
  expect(errors).toEqual([]);
});
