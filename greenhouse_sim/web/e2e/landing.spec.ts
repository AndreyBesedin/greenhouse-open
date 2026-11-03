import { expect, type Page, test } from "@playwright/test";
import { LANDING_PATH, REPOSITORY_URL, VIEWER_PATH } from "../src/landing/paths";

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

test("the bare address is the page where a person decides what to do", async ({ page }) => {
  const errors = collectErrors(page);

  await page.goto(LANDING_PATH);

  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  const contribute = page.getByRole("link", { name: "Contribute" });
  await expect(contribute).toHaveAttribute("href", REPOSITORY_URL);
  await expect(contribute).toHaveAttribute("target", "_blank");
  await expect(contribute).toHaveAttribute("rel", /noopener/);
  await expect(page.getByRole("link", { name: "Open the builder" })).toHaveAttribute(
    "href",
    "/builder",
  );
  // The runs kept are told, with what their objects hold, or that none is
  // kept (the specs share a simulator, so which of the two is not asked).
  await expect(
    page.getByText(/No run has been kept yet|\d+ runs? kept, [\d.]+ (B|kB|MB)/),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("a scenario is searched for and opened in the viewer", async ({ page }) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });

  await search.click();
  await expect(page.getByRole("option", { name: /Climate box/ })).toBeVisible();
  await search.fill("climate_box");
  await expect(page.getByRole("option")).toHaveCount(2);
  await search.press("Enter");

  // The scenario's runs are in a dialog, from which the viewer opens on it.
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toContainText("Climate box");
  await dialog.getByRole("link", { name: "Open in the viewer" }).click();

  await expect(page).toHaveURL(/\/view\?scenario=climate_box$/);
  await expect(page.locator("canvas")).toBeVisible();
});

test("the viewer is at its own address, and an address with a query is still the viewer", async ({
  page,
}) => {
  // A page loaded directly at a path below the root, and the links made
  // before the landing page existed.
  await page.goto(VIEWER_PATH);
  await expect(page.getByRole("heading", { name: "greenhouse-sim viewer" })).toBeVisible();

  await page.goto("/?scenario=climate_box");
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0");
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toHaveCount(0);
});

test("a run is started at a seed from a scenario's dialog, listed, and not removed while it computes", async ({
  page,
}) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill("solar_lab");
  await search.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toContainText("Solar");

  await dialog.getByRole("button", { name: "New run" }).click();
  // Exactly: the runs of the scenario that other specs have started have labels that say a seed.
  await dialog.getByLabel("Seed", { exact: true }).fill("7");
  await dialog.getByLabel("Seconds per simulated day").fill("1");
  await dialog.getByRole("button", { name: "Start run" }).click();

  await expect(dialog.getByRole("link", { name: "Follow it in the viewer" })).toBeVisible();
  const row = dialog.locator(".landing-run").filter({ hasText: "Seed 7" });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: /^Delete the run with seed 7/ }).click();
  await dialog.getByRole("button", { name: /^Delete the run with seed 7/ }).click();
  await expect(dialog.getByRole("alert")).toContainText("being computed");
  await expect(row).toBeVisible();

  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
