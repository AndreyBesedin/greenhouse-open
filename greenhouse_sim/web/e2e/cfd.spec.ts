import { expect, test } from "@playwright/test";

test("a scenario's CFD boundaries are drawn by category, and follow its openings", async ({
  page,
}) => {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/cfd/geometry")) {
      asked.push(new URL(request.url()).search);
    }
  });
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001");
  const canvas = page.locator("canvas");
  const before = await canvas.screenshot();
  const legend = page.getByRole("figure", { name: "CFD boundaries" });

  await page.getByRole("checkbox", { name: "CFD boundaries" }).check();

  await expect(page).toHaveURL(/\?scenario=gh_001&cfd=boundaries$/);
  // gh_001's field box, with its two roof vents open a little, its door
  // shut, its irrigation unit in the way, and its crop's slabs and supports
  // too narrow for cells of up to 0.5 m.
  await expect(page.getByTestId("cfd-status")).toHaveText(
    "16 × 20 × 7 cells, 2 openings, 1 obstacle removing 6 cells; 24 fixtures too small to remove a cell.",
  );
  await expect(legend.getByTestId("cfd-category")).toHaveText([
    "floor: 320 faces",
    "wall ×4: 504 faces",
    "ceiling, at the eaves: 320 faces",
    "opening ×2: 24 faces",
    "obstacle: 6 cells",
  ]);
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);

  // Opening the door makes it a third opening, 2 faces wide and 4 high.
  const door = page.getByTestId("opening-door_1").locator("..").getByRole("slider");
  await door.fill("100");
  await expect(page).toHaveURL(/\?scenario=gh_001&open=door_1:1&cfd=boundaries$/);
  await expect(legend.getByTestId("cfd-category").nth(3)).toHaveText("opening ×3: 32 faces");
  expect(asked).toEqual(["", "?open=door_1:1"]);

  await page.getByRole("checkbox", { name: "CFD boundaries" }).uncheck();
  await expect(page).toHaveURL(/\?scenario=gh_001&open=door_1:1$/);
  await expect(legend).toHaveCount(0);
  await expect(page.getByTestId("cfd-status")).toHaveCount(0);
});
