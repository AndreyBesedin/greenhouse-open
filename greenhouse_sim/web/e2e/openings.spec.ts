import { expect, test } from "@playwright/test";

test("a slider opens a roof vent, through the simulator, and the address keeps it", async ({
  page,
}) => {
  const scenes: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/scene")) {
      scenes.push(new URL(request.url()).search);
    }
  });
  await page.goto("/?scenario=gh_demo");
  const openings = page.getByRole("group", { name: "Openings" });
  const vent = page.getByTestId("opening-roof_vent_1");
  await expect(vent).toHaveText("25%, 0.26 m²");

  await openings.getByRole("slider").first().fill("100");

  // Wide open, the vent's curtain would pass its 1.6 by 0.6 m frame.
  await expect(vent).toHaveText("100%, 0.96 m²");
  await expect(page).toHaveURL(/\?scenario=gh_demo&open=roof_vent_1:1$/);
  expect(scenes).toContain("?open=roof_vent_1:1");

  await page.reload();
  await expect(vent).toHaveText("100%, 0.96 m²");
  await expect(page.getByTestId("opening-roof_vent_2")).toHaveText("25%, 0.26 m²");
});
