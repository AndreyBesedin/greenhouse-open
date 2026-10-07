import { expect, test } from "@playwright/test";

import { onScreen } from "./view";

// The P04 airflow QA case, read at two probes: upstream of its block and in
// its wake, as OpenFOAM solved it, against the uniform breeze it is compared
// with (tests/golden/airflow_box_probes.json holds the same points).
const PROBED = "/?scenario=airflow_box&field=cfd&compare=uniform&probes=3:3.2:0.75,7:3.2:0.75";

test("probes read the drawn field and compare it with another", async ({ page }) => {
  await page.goto(PROBED);

  await expect(page.getByTestId("probe-1-reading")).toHaveText(
    "cfd: 0.43 m/s (0.42, 0.00, 0.06), pressure 0.21 Pa",
  );
  await expect(page.getByTestId("probe-1-compared")).toHaveText(
    "uniform: 0.50 m/s (0.50, 0.00, 0.00), temperature 20.00 °C",
  );
  // Upstream, the solved air is a little slower than the breeze, and rises
  // a little towards the block.
  await expect(page.getByTestId("probe-1-difference")).toHaveText(
    /^cfd − uniform: -0\.07 m\/s, turned 7\.9\d°$/,
  );
  // In the wake, it is nearly still, and turned back.
  await expect(page.getByTestId("probe-2-reading")).toHaveText(
    "cfd: 0.02 m/s (-0.01, 0.00, 0.01), pressure 0.19 Pa",
  );
  await expect(page.getByTestId("probe-2-difference")).toHaveText(
    /^cfd − uniform: -0\.48 m\/s, turned 1[23]\d\.\d\d°$/,
  );
  // Each is marked in the view, by name.
  await expect(page.getByTestId("debug-label")).toHaveText(["P1", "P2"]);

  // Compared with nothing, only the drawn field is read.
  await page.getByRole("combobox", { name: "Compare with" }).selectOption("none");
  await expect(page).toHaveURL(/&field=cfd&probes=3:3\.2:0\.75,7:3\.2:0\.75$/);
  await expect(page.getByTestId("probe-1-compared")).toHaveCount(0);
});

test("a probe is placed by clicking the view, moved, and removed", async ({ page }) => {
  await page.goto("/?scenario=airflow_box&field=cfd");
  await expect(page.getByTestId("field-status")).toContainText("airflow_box_cfd");
  const probes = page.getByRole("group", { name: "Probes" });

  // Added in the field's middle: halfway along, across and up the house.
  await probes.getByRole("button", { name: "Add a probe" }).click();
  await expect(page).toHaveURL(/&probes=6:3\.2\d*:1\.5$/);

  // Placed where the view is clicked, 1 m above the ground there.
  await probes.getByRole("checkbox", { name: /place by clicking/ }).check();
  const ground = await onScreen(page, { x: 1.5, y: 1.5, z: 0 });
  await page.mouse.click(ground.x, ground.y);
  await expect(page.getByTestId("probe-2")).toBeVisible();
  await expect(probes.getByRole("spinbutton", { name: "P2 x" })).toHaveValue(/^1\.[45]\d$/);
  await expect(probes.getByRole("spinbutton", { name: "P2 z" })).toHaveValue("1");
  // A click that places a probe selects nothing.
  await expect(page.getByRole("region", { name: "Inspector" })).toHaveCount(0);

  await probes.getByRole("spinbutton", { name: "P1 z" }).fill("2.5");
  await expect(page).toHaveURL(/&probes=6:3\.2\d*:2\.5,1\.[45]\d*:1\.[45]\d*:1$/);
  await probes.getByRole("button", { name: "Remove P1" }).click();
  await expect(page.getByTestId("probe-2")).toHaveCount(0);
  await expect(page.getByTestId("debug-label")).toHaveText(["P1"]);
});
