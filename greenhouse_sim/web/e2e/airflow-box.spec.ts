import { expect, test } from "@playwright/test";

// The P04 final QA, `airflow-box`, as a walk through the airflow QA case:
// air blown from door to door past a block, solved with OpenFOAM, drawn as
// arrows and streamlines, read at probes against the prescribed breeze it is
// compared with, and with its block taken away and put back. Its screenshots
// are e2e/visual/airflow.spec.ts.
const PROBES = "3:3.2:0.75,5.5:1:0.75,7:3.2:0.75";

test("its air is drawn as arrows or streamlines, solved or prescribed", async ({ page }) => {
  const status = page.getByTestId("field-status");
  const fieldChoice = page.getByRole("combobox", { name: "Air field" });
  await page.goto("/?scenario=airflow_box");

  await fieldChoice.selectOption("cfd");
  await expect(status).toHaveText(
    "airflow_box_cfd (openfoam:simpleFoam v2412): 24 × 13 × 6 cells, air speed 0 to 0.60 m/s.",
  );
  await expect(page.getByRole("radio", { name: "arrows" })).toBeChecked();
  await page.getByRole("radio", { name: "streamlines" }).check();
  await expect(page).toHaveURL(/\?scenario=airflow_box&field=cfd&fieldView=streamlines$/);
  await page.getByRole("radio", { name: "arrows" }).check();

  // The breeze it is compared with: the inlet's speed, everywhere.
  await fieldChoice.selectOption("uniform");
  await expect(status).toHaveText(
    "airflow_box_uniform (prescribed:uniform): 24 × 13 × 6 cells, air speed 0.50 to 0.50 m/s.",
  );
  await fieldChoice.selectOption("cfd");
  await expect(status).toContainText("openfoam:simpleFoam");
});

test("probes read the solution against the breeze, with the block and without it", async ({
  page,
}) => {
  const reading = (probe: number) => page.getByTestId(`probe-${probe}-reading`);
  await page.goto(`/?scenario=airflow_box&field=cfd&compare=uniform&probes=${PROBES}`);

  // Upstream, beside the block, and in its wake.
  await expect(reading(1)).toHaveText("cfd: 0.43 m/s (0.42, 0.00, 0.06), pressure 0.21 Pa");
  await expect(reading(2)).toHaveText("cfd: 0.21 m/s (0.19, -0.09, 0.02), pressure 0.19 Pa");
  await expect(reading(3)).toHaveText("cfd: 0.02 m/s (-0.01, 0.00, 0.01), pressure 0.19 Pa");
  await expect(page.getByTestId("probe-3-difference")).toHaveText(
    /^cfd − uniform: -0\.48 m\/s, turned 1[23]\d\.\d\d°$/,
  );

  // Taken away, the block no longer turns the air: beside where it stood the
  // air is slower, and behind it the air runs on down the house.
  const layout = page.getByRole("combobox", { name: "Layout of airflow_box" });
  await layout.selectOption("open");
  await expect(page).toHaveURL(
    `/?scenario=airflow_box&layout=open&field=cfd&compare=uniform&probes=${PROBES}`,
  );
  await expect(reading(2)).toHaveText("cfd: 0.07 m/s (0.06, -0.02, 0.01), pressure 0.16 Pa");
  await expect(reading(3)).toHaveText("cfd: 0.29 m/s (0.29, 0.00, 0.01), pressure 0.16 Pa");

  // Put back, it turns the air again.
  await layout.selectOption("default");
  await expect(reading(3)).toHaveText("cfd: 0.02 m/s (-0.01, 0.00, 0.01), pressure 0.19 Pa");
});

test("the QA page draws the solution's vectors and a slice of its speed", async ({ page }) => {
  await page.goto("/qa/airflow-box");
  await expect(page.getByTestId("qa-caption")).toHaveText("Airflow QA, vectors view");
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("air speed (m/s)");

  await page.goto("/qa/airflow-box?view=slice");
  await expect(page.getByTestId("qa-caption")).toHaveText("Airflow QA, slice view");

  await page.goto("/qa/airflow-box?view=wake");
  await expect(page.getByRole("alert")).toHaveText("The view must be vectors or slice.");
});
