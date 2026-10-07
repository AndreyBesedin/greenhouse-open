import { expect, type Page, test } from "@playwright/test";

// The HUD samples the scene a few times a second, and counts its objects.
const SAMPLE_WAIT_MS = 1_000;
// Drawing in software on CI can take a while.
const DRAWN_TIMEOUT_MS = 30_000;

async function objectCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("object-count").textContent());
}

/** The scene's object count once it has stopped changing. */
async function settledObjectCount(page: Page): Promise<number> {
  let last = Number.NaN;
  await expect
    .poll(
      async () => {
        const now = await objectCount(page);
        const settled = now === last;
        last = now;
        return settled;
      },
      { intervals: [SAMPLE_WAIT_MS], timeout: DRAWN_TIMEOUT_MS },
    )
    .toBe(true);
  return last;
}

test("a scenario's CFD boundaries are drawn by category, and follow its openings", async ({
  page,
}) => {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/cfd/geometry")) {
      asked.push(new URL(request.url()).search);
    }
  });
  await page.goto("/?scenario=tomato_compartment");
  await expect(page.getByTestId("scene-status")).toContainText("tomato_compartment");
  const legend = page.getByRole("figure", { name: "CFD boundaries" });

  await page.getByRole("checkbox", { name: "CFD boundaries" }).check();

  await expect(page).toHaveURL(/\?scenario=tomato_compartment&cfd=boundaries$/);
  // The compartment's field box, with its four roof vents open a little, its
  // door shut, its irrigation unit in the way, and its crop's slabs, supports
  // and legs too narrow for cells of up to 0.5 m.
  await expect(page.getByTestId("cfd-status")).toHaveText(
    "48 × 32 × 12 cells, 4 openings, 1 obstacle removing 6 cells; 104 fixtures too small to remove a cell.",
  );
  await expect(legend.getByTestId("cfd-category")).toHaveText([
    "floor: 1536 faces",
    "wall ×4: 1920 faces",
    "ceiling, at the eaves: 1536 faces",
    "opening ×4: 96 faces",
    "obstacle: 6 cells",
  ]);

  // Opening the door makes it a fifth opening, 6 faces wide and 6 high.
  const door = page.getByTestId("opening-door_front").locator("..").getByRole("slider");
  await door.fill("100");
  await expect(page).toHaveURL(/\?scenario=tomato_compartment&open=door_front:1&cfd=boundaries$/);
  await expect(legend.getByTestId("cfd-category").nth(3)).toHaveText("opening ×5: 132 faces");
  expect(asked).toEqual(["", "?open=door_front:1"]);

  // Drawn, the boundaries are a group of their twelve fills and their
  // outlines.
  const drawn = await settledObjectCount(page);
  await page.getByRole("checkbox", { name: "CFD boundaries" }).uncheck();
  await expect(page).toHaveURL(/\?scenario=tomato_compartment&open=door_front:1$/);
  await expect.poll(() => objectCount(page), { timeout: DRAWN_TIMEOUT_MS }).toBe(drawn - 14);
  await expect(legend).toHaveCount(0);
  await expect(page.getByTestId("cfd-status")).toHaveCount(0);
});
