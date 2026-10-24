import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

// The setup builder (P12.2): a house drafted from the first form and drawn,
// its rows given another crop and that undone, saved, exported, run as a
// scenario the viewer opens, reopened from the drafts and imported again.
// The simulator served keeps its drafts in a file of the test run's own.

// On CI the simulator may still be working out what the spec before this
// one asked for.
const ARRIVES = { timeout: 60_000 };

function field(page: Page, label: string) {
  return page.locator(".builder-form").getByLabel(label, { exact: true });
}

test("builder: a house drafted, edited, saved, exported, run, reopened and imported", async ({
  page,
}) => {
  test.setTimeout(240_000);
  // Its own identifier, so that a retry against the same simulator drafts
  // a house of its own.
  const id = `e2e_${Date.now()}`;
  const status = page.getByTestId("builder-status");
  const runnable = page.getByTestId("builder-runnable");

  await page.goto("/builder");
  await expect(page.getByRole("heading", { name: "Setup builder" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "A new house" })).toBeVisible();
  await expect(field(page, "Length (m)")).toHaveValue("12");

  // The first form, by keyboard: its identifier typed, and Enter drafts it.
  await field(page, "Identifier").fill(id);
  await field(page, "Name").fill("The test house");
  await field(page, "Crop rows").fill("3");
  await field(page, "Crop rows").press("Enter");
  await expect(status).toHaveText("Drafted The test house; not saved yet.", ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(`The test house (${id}), not saved`);
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await expect(page.locator(".builder-findings li")).toHaveText([
    "Warning: No door.",
    "Warning: No vent.",
    "Warning: No heater.",
    "Warning: No circulation fan.",
  ]);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);
  await expect(page.locator(".builder-rows tbody tr")).toHaveCount(3);

  // Row 2 given another variety: a run grows one crop, so it cannot run;
  // undone and redone in one step each, by button and by keyboard.
  await page.getByLabel("Choose row 2").check();
  await page.locator(".builder-give").getByLabel("Variety").fill("beefsteak");
  await page.getByRole("button", { name: "Give the chosen rows this crop" }).click();
  await expect(status).toHaveText("Rows 2 grow simple beefsteak.");
  await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
  await expect(page.locator(".builder-finding-error")).toContainText("Rows grow different crops");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
  await page.locator("body").press("ControlOrMeta+z");
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await expect(page.getByRole("button", { name: "Run this revision" })).toBeDisabled();

  // Saved: the first revision of a new draft.
  await page.getByRole("button", { name: "Save" }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(`The test house (${id}), revision 1`);
  await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();

  // Exported, as a file an import reads.
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(`${id}.json`);
  const exported = await download.path();
  const file = JSON.parse(readFileSync(exported, "utf8"));
  expect([file.installation_id, file.name, file.row_crops.length]).toEqual([
    id,
    "The test house",
    3,
  ]);
  expect(typeof file.schema_version).toBe("number");

  // Run as a scenario of its own, which the viewer opens.
  await page.locator(".builder-run").getByLabel("Days").fill("3");
  await page.getByRole("button", { name: "Run this revision" }).click();
  await expect(status).toContainText(`Its run is registered as ${id}_r1.`, ARRIVES);
  await page.getByRole("link", { name: "Open The test house in the viewer" }).click();
  await expect(page).toHaveURL(new RegExp(`scenario=${id}_r1`));
  await expect(page.getByTestId("scene-status")).toContainText(`${id}_r1`, ARRIVES);

  // Back in the builder: the draft is kept, and reopens as saved.
  await page.goto("/builder");
  await page.getByRole("button", { name: "The test house" }).click();
  await expect(status).toHaveText("Opened The test house, revision 1.", ARRIVES);
  await expect(page.locator(".builder-rows tbody tr")).toHaveCount(3);

  // Imported again from its file: a draft not saved yet.
  await page.getByRole("button", { name: "Start again" }).click();
  await page.locator(".builder-start input[type=file]").setInputFiles({
    name: download.suggestedFilename(),
    mimeType: "application/json",
    buffer: readFileSync(exported),
  });
  // A draft of that identifier is kept: renamed, it is saved as another.
  await expect(status).toHaveText(
    `Imported The test house from ${download.suggestedFilename()}; not saved yet. ` +
      `A draft ${id} is kept already: rename this one to save it.`,
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toHaveText(`The test house (${id}), not saved`);
  const identity = page.locator(".builder-identity");
  await identity.getByLabel("Identifier").fill(`${id}_b`);
  await identity.getByRole("button", { name: "Rename" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(
    `The test house (${id}_b), revision 1`,
  );
});

test("builder: values no greenhouse can have are refused by field", async ({ page }) => {
  await page.goto("/builder");
  await page.locator(".builder-form").getByLabel("Height to the ridge (m)").fill("3");
  await page.getByRole("button", { name: "Draft this house" }).click();

  await expect(page.getByTestId("builder-status")).toContainText(
    "The house cannot be drafted:",
    ARRIVES,
  );
  await expect(page.getByRole("heading", { name: "A new house" })).toBeVisible();
});

test("builder: a scenario's house copied under an identifier of its own, and saved", async ({
  page,
}) => {
  const id = `climate_copy_${Date.now()}`;
  const status = page.getByTestId("builder-status");
  await page.goto("/builder");
  const copy = page.locator(".builder-copy");
  await copy.getByLabel("Scenario").selectOption({ label: "Climate box" });
  await expect(copy.getByLabel("The copy's identifier")).toHaveValue("climate_box_copy");
  await copy.getByLabel("The copy's identifier").fill(id);
  await copy.getByRole("button", { name: "Copy its house" }).click();

  await expect(status).toHaveText(`Copied Climate box's house as ${id}; not saved yet.`, ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(
    `Climate box (copy) (${id}), not saved`,
  );
  // Its door, vents, heater and fans come with it: nothing it lacks.
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  await expect(page.locator(".builder-findings li")).toHaveCount(0);
  await expect(page.locator(".builder-rows tbody tr")).toHaveCount(2);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);

  await page.getByRole("button", { name: "Save" }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
});

test("builder: vents spread along the roof and heaters placed at a step, each undone in one step", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const status = page.getByTestId("builder-status");
  const items = page.locator(".builder-items");
  const palette = page.locator(".builder-palette");

  await page.goto("/builder");
  await page.locator(".builder-form").getByLabel("Identifier").fill(`items_${Date.now()}`);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);

  // A row of four roof vents along each slope of the first span, in one edit.
  await palette.getByLabel("What").selectOption("roof_vent");
  await palette.getByLabel("roof 1 right").check(ARRIVES);
  await palette.getByLabel("roof 1 left").check();
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 4 roof vents on 2 surfaces.", ARRIVES);
  await expect(items.locator("tbody tr")).toHaveCount(8);
  await expect(page.locator(".builder-findings li")).not.toContainText(["Warning: No vent."]);

  // Three heaters along the house, two metres apart, by the right wall.
  await palette.getByLabel("What").selectOption("heater");
  await palette.getByLabel("y (m)", { exact: true }).fill("0.6");
  await palette.getByLabel("How many", { exact: true }).fill("3");
  await palette.getByLabel("Step along x (m)").fill("2");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 3 heaters.", ARRIVES);
  await expect(items.locator("tbody tr")).toHaveCount(11);
  await expect(items.getByRole("cell", { name: "heater_3", exact: true })).toBeVisible();

  // Undone: the heaters go in one step, the vents stay.
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(items.locator("tbody tr")).toHaveCount(8);
});

test("builder: the inspector sets a field of the item chosen, and of the house", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const status = page.getByTestId("builder-status");
  const house = page.locator(".builder-inspector").first();
  const inspector = page.locator(".builder-items .builder-inspector");
  const palette = page.locator(".builder-palette");

  await page.goto("/builder");
  await page.locator(".builder-form").getByLabel("Identifier").fill(`inspect_${Date.now()}`);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // No item chosen: the house's own fields.
  await expect(house.getByRole("heading", { name: "Envelope and rows" })).toBeVisible();
  await house.getByLabel("Length", { exact: true }).fill("14");
  await house.getByLabel("Length", { exact: true }).press("Enter");
  await expect(status).toHaveText("Set length of the house.", ARRIVES);
  await expect(house.getByLabel("Length", { exact: true })).toHaveValue("14");

  // A heater placed and chosen: its fields, one changed by its path.
  await palette.getByLabel("What").selectOption("heater");
  await palette.getByLabel("y (m)", { exact: true }).fill("0.6");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 heater.", ARRIVES);
  await page.getByLabel("Choose heater_1").check();
  await expect(inspector.getByRole("heading", { name: "heater_1" })).toBeVisible();
  await inspector.getByLabel("Power W").fill("20000");
  await inspector.getByLabel("Power W").press("Enter");
  await expect(status).toHaveText("Set power w of heater_1.", ARRIVES);
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // A second heater placed where the first stands: an error naming both,
  // the heaters outlined on the house.
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 heater.", ARRIVES);
  await expect(page.locator(".builder-finding-error")).toContainText(
    "Equipment through another item: heater_1 with heater_2.",
    ARRIVES,
  );
});

test("builder: heating pipes and a service zone placed, and changed in the inspector", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const status = page.getByTestId("builder-status");
  const items = page.locator(".builder-items");
  const inspector = page.locator(".builder-items .builder-inspector");
  const palette = page.locator(".builder-palette");

  await page.goto("/builder");
  await page.locator(".builder-form").getByLabel("Identifier").fill(`fixtures_${Date.now()}`);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // A run of heating pipes, laid along the house just above the floor.
  await palette.getByLabel("What").selectOption("pipe_run");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 pipe run.", ARRIVES);
  await expect(items.getByRole("cell", { name: "pipe run", exact: true })).toBeVisible();
  await page.getByLabel("Choose pipes_1").check();
  await expect(inspector.getByRole("heading", { name: "pipes_1" })).toBeVisible();
  await inspector.getByLabel("Count").fill("3");
  await inspector.getByLabel("Count").press("Enter");
  await expect(status).toHaveText("Set count of pipes_1.", ARRIVES);

  // A service zone, widened by its area's width.
  await page.getByLabel("Choose pipes_1").uncheck();
  await palette.getByLabel("What").selectOption("service_zone");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 service zone.", ARRIVES);
  await page.getByLabel("Choose service_zone_1").check();
  await inspector.getByLabel("Area Width").fill("1.5");
  await inspector.getByLabel("Area Width").press("Enter");
  await expect(status).toHaveText("Set area width of service_zone_1.", ARRIVES);
  await expect(inspector.getByLabel("Area Width")).toHaveValue("1.5");
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
});
