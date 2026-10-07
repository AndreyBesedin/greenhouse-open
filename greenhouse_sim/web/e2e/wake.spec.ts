import { expect, test } from "@playwright/test";

// The P04 airflow QA case: air blown through `airflow_box` from door to door,
// with a block on the floor between them, and without it (`&layout=open`).
// Its streamlines are drawn from OpenFOAM's solutions, kept for each layout.
test("airflow_box's air is solved with its block, and without it", async ({ page }) => {
  const status = page.getByTestId("field-status");
  await page.goto("/?scenario=airflow_box&field=cfd&fieldView=streamlines");

  // Still inside the block; fastest where the air squeezes past it.
  await expect(status).toHaveText(
    "airflow_box_cfd (openfoam:simpleFoam v2412): 24 × 13 × 6 cells, air speed 0 to 0.60 m/s.",
  );
  await expect(page.getByRole("combobox", { name: "Air field" }).locator("option")).toHaveText([
    "none",
    "uniform, the scenario's airflow",
    "buoyancy",
    "vortex",
    "cfd",
    "shear",
  ]);

  // Without it, the air moves everywhere, a little faster down the middle.
  await page.goto("/?scenario=airflow_box&layout=open&field=cfd&fieldView=streamlines");
  await expect(status).toHaveText(
    "airflow_box_cfd (openfoam:simpleFoam v2412): 24 × 13 × 6 cells, air speed 0.00 to 0.61 m/s.",
  );
  await expect(page).toHaveURL(
    /\?scenario=airflow_box&layout=open&field=cfd&fieldView=streamlines$/,
  );
});
