import { expect, test } from "@playwright/test";
import { LANDING_PATH, viewerAddress } from "../src/landing/paths";

const MIN_TARGET_PX = 44;

test("the viewer has a Home button at the top left that opens the landing page", async ({
  page,
}) => {
  await page.goto(viewerAddress("climate_box"));

  const home = page.getByRole("link", { name: "Home" });
  await expect(home).toBeVisible();
  const box = await home.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(MIN_TARGET_PX);
  expect(box?.width ?? 0).toBeGreaterThanOrEqual(MIN_TARGET_PX);
  expect(box?.x ?? Infinity).toBeLessThan(MIN_TARGET_PX * 2);

  // It is a link, so a keyboard reaches it and Enter follows it.
  await home.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL((url) => url.pathname === LANDING_PATH && url.search === "");
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
});

test("the viewer does not show the line that says which scenario is shown", async ({ page }) => {
  await page.goto(viewerAddress("climate_box"));
  const status = page.getByTestId("scene-status");
  // The scene has arrived: it is announced, in the status, for whoever hears the page.
  await expect(status).toContainText("climate_box, day 0");
  await expect(status).toHaveAttribute("role", "status");

  // And not shown: the text is clipped to a point.
  const box = await status.boundingBox();
  expect(box?.width ?? Infinity).toBeLessThanOrEqual(1);
  expect(box?.height ?? Infinity).toBeLessThanOrEqual(1);
  await expect(page.locator(".source-chooser > summary")).toContainText("Choose what to show");
});
