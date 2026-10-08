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
  await page.goto("/?scenario=climate_box");
  const openings = page.getByRole("group", { name: "Openings" });
  const vent = page.getByTestId("opening-roof_vent");
  // The climate box's roof vent, shut to start.
  await expect(vent).toHaveText("0%, 0 m²");

  await openings.getByRole("slider").first().fill("100");

  // Wide open, at 45°, the 4 by 1 m vent's curtain: the gap along its free
  // edge and the two triangles at its sides.
  await expect(vent).toHaveText("100%, 3.77 m²");
  await expect(page).toHaveURL(/\?scenario=climate_box&open=roof_vent:1$/);
  expect(scenes).toContain("?open=roof_vent:1");

  await page.reload();
  await expect(vent).toHaveText("100%, 3.77 m²");
  await expect(page.getByTestId("opening-side_vent")).toHaveText("0%, 0 m²");
});
