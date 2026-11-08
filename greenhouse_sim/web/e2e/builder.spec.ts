import { readFileSync } from "node:fs";

import { expect, type Locator, type Page, test } from "@playwright/test";

import { lowContrast } from "./contrast.ts";

// The setup builder (P12.2): a house drafted from the first form and drawn,
// its rows given another crop and that undone, saved, exported, run as a
// scenario the viewer opens, reopened from the drafts and imported again.
// The simulator served keeps its drafts in a file of the test run's own.

// On CI the simulator may still be working out what the spec before this
// one asked for.
const ARRIVES = { timeout: 60_000 };

const PHONE = { width: 390, height: 844 };
// A compact control's least height and width (`--target-compact`, P19.9), and a
// target's, which the ways out of the builder keep.
const COMPACT_TARGET_PX = 24;
const TARGET_PX = 44;
// What a pointer is to hit: a box to tick is the browser's, and left out.
const CONTROLS = 'button, select, input:not([type="checkbox"]):not([type="file"])';

/** One of the builder's forms, by its heading. */
function form(page: Page, name: string): Locator {
  return page.getByRole("form", { name, exact: true });
}

/** One of the builder's sections, by its heading. */
function region(page: Page, name: string): Locator {
  return page.getByRole("region", { name, exact: true });
}

/** The rows of a section's table, its header left out. */
function bodyRows(page: Page, section: string): Locator {
  return region(page, section)
    .getByRole("row")
    .filter({ has: page.getByRole("cell") });
}

/** What the draft needs, each finding a line. */
function findings(page: Page): Locator {
  return region(page, "What it needs").getByRole("listitem");
}

function errors(page: Page): Locator {
  return findings(page).filter({ hasText: /^Error:/ });
}

function field(page: Page, label: string) {
  return form(page, "A new house").getByLabel(label, { exact: true });
}

/** How wide the page is, with whatever overflows its window. */
function pageWidth(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth);
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
  await expect(findings(page)).toHaveText([
    "Warning: No door.",
    "Warning: No vent.",
    "Warning: No heater.",
    "Warning: No circulation fan.",
  ]);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);
  await expect(bodyRows(page, "Rows")).toHaveCount(3);

  // Row 2 given another variety: a run grows one crop, so it cannot run;
  // undone and redone in one step each, by button and by keyboard.
  await page.getByLabel("Choose row 2").check();
  await region(page, "Rows").getByLabel("Variety").fill("beefsteak");
  await page.getByRole("button", { name: "Give the chosen rows this crop" }).click();
  await expect(status).toHaveText("Rows 2 grow simple beefsteak.");
  await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
  await expect(errors(page)).toContainText("Rows grow different crops");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
  await page.locator("body").press("ControlOrMeta+z");
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await expect(page.getByRole("button", { name: "Run this revision" })).toBeDisabled();

  // Saved: the first revision of a new draft.
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(`The test house (${id}), revision 1`);
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();

  // Exported, as a file an import reads.
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download house file" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(`${id}.house.json`);
  const exported = await download.path();
  const file = JSON.parse(readFileSync(exported, "utf8"));
  expect([file.installation_id, file.name, file.row_crops.length]).toEqual([
    id,
    "The test house",
    3,
  ]);
  expect(typeof file.schema_version).toBe("number");

  // Run as a scenario of its own, which the viewer opens.
  await form(page, "Run it").getByLabel("Days").fill("3");
  await page.getByRole("button", { name: "Run this revision" }).click();
  await expect(status).toContainText(`Its run is registered as ${id}_r1.`, ARRIVES);
  // Where to go from there: to a run of it, or back to the page that chooses.
  await expect(page.getByRole("link", { name: "Start a run of it" })).toHaveAttribute(
    "href",
    `/#run=${id}_r1`,
  );
  await expect(page.getByRole("link", { name: "Back to the start" })).toHaveAttribute("href", "/");
  // The scenario is a file to share: downloaded as the simulator writes it.
  const sharing = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download scenario file" }).click();
  const shared = await sharing;
  expect(shared.suggestedFilename()).toBe(`${id}_r1.scenario.json`);
  const sharedFile = JSON.parse(readFileSync(await shared.path(), "utf8"));
  expect(typeof sharedFile.schema_version).toBe("number");
  await page.getByRole("link", { name: "Open The test house in the viewer" }).click();
  await expect(page).toHaveURL(new RegExp(`scenario=${id}_r1`));
  await expect(page.getByTestId("scene-status")).toContainText(`${id}_r1`, ARRIVES);

  // The scenario it registered is one a run is started of, from the page that
  // chooses: the builder's second link opens its new-run form.
  await page.goto(`/#run=${id}_r1`);
  await expect(page.getByRole("dialog", { name: "The test house" })).toBeVisible(ARRIVES);
  await expect(page.getByRole("button", { name: "Start run" })).toBeVisible();

  // Back in the builder: the draft is kept, and reopens as saved.
  await page.goto("/builder");
  await page.getByRole("button", { name: "The test house" }).click();
  await expect(status).toHaveText("Opened The test house, revision 1.", ARRIVES);
  await expect(bodyRows(page, "Rows")).toHaveCount(3);

  // Imported again from its file: a draft not saved yet.
  await page.getByRole("button", { name: "Start again" }).click();
  await region(page, "Drafts kept")
    .locator('input[type="file"]')
    .setInputFiles({
      name: download.suggestedFilename(),
      mimeType: "application/json",
      buffer: readFileSync(exported),
    });
  // A draft of that identifier is kept: renamed, it is saved as another.
  await expect(status).toHaveText(
    `Imported The test house from ${download.suggestedFilename()}, a house file: it holds no run settings; not saved yet. ` +
      `A draft with the identifier ${id} is kept already: change this one's identifier to save it.`,
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toHaveText(`The test house (${id}), not saved`);
  const identity = form(page, "The house");
  await identity.getByLabel("Identifier").fill(`${id}_b`);
  await identity.getByRole("button", { name: "Rename" }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  await expect(page.getByTestId("builder-draft")).toHaveText(
    `The test house (${id}_b), revision 1`,
  );
});

test("builder: a draft saved and a run of it started in one step, on a worker, in its replay", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const id = `finish_${Date.now()}`;
  await page.goto("/builder");
  // A house of its own name: the scenario this registers is listed by the start
  // page, whose searches the other specs make by a packaged scenario's name.
  await field(page, "Identifier").fill(id);
  await field(page, "Name").fill("Finishing house");
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // The run step's days are kept for the run the one step makes.
  await form(page, "Run it").getByLabel("Days").fill("2");
  await page.getByRole("button", { name: "Save and start a run" }).click();

  await expect(page).toHaveURL(new RegExp(`/replay\\?run=${id}_r1.*follow=1`), ARRIVES);
  await expect(page.getByTestId("replay-status")).toHaveText(/Queued|Running|Finished/, ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText(`${id}_r1`, ARRIVES);
  // A worker computes it, which knows the scenario only from the store.
  await expect
    .poll(
      async () =>
        Number(
          await page
            .getByRole("slider", { name: "Position in the run" })
            .getAttribute("aria-valuemax"),
        ),
      { timeout: 90_000 },
    )
    .toBeGreaterThan(0);
  await expect(page.getByTestId("replay-status")).toHaveText(/Running|Finished/);
  // A house with no equipment has a climate run as any other: the replay draws it,
  // and no moment of the run is said not to be drawn.
  await expect(page.getByTestId("climate-failed")).toHaveCount(0);
  await expect(page.getByText("cannot be read")).toHaveCount(0);
});

test("builder: a draft saved and the start page reached in one step", async ({ page }) => {
  const id = `leave_${Date.now()}`;
  await page.goto("/builder");
  await form(page, "A new house").getByLabel("Identifier").fill(id);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  await page.getByRole("button", { name: "Save and go back" }).click();

  await expect(page).toHaveURL(/\/$/, ARRIVES);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible(
    ARRIVES,
  );
  // The draft was saved: the builder lists it.
  await page.goto("/builder");
  await expect(page.getByRole("button", { name: "My greenhouse" }).first()).toBeVisible(ARRIVES);
});

test("builder: values no greenhouse can have are refused by field", async ({ page }) => {
  await page.goto("/builder");
  await form(page, "A new house").getByLabel("Height to the ridge (m)").fill("3");
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
  const copy = form(page, "Or copy a scenario's house");
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
  await expect(findings(page)).toHaveCount(0);
  await expect(bodyRows(page, "Rows")).toHaveCount(2);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);

  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
});

test("builder: vents spread along the roof and heaters placed at a step, each undone in one step", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const status = page.getByTestId("builder-status");
  const items = region(page, "Items of the house");
  const palette = form(page, "Place");

  await page.goto("/builder");
  await form(page, "A new house").getByLabel("Identifier").fill(`items_${Date.now()}`);
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
  await expect(findings(page)).not.toContainText(["Warning: No vent."]);

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
  const house = region(page, "Envelope and rows");
  // The inspector of the one item chosen, under the items.
  const inspector = (item: string) =>
    region(page, "Items of the house").getByRole("region", { name: item, exact: true });
  const palette = form(page, "Place");

  await page.goto("/builder");
  await form(page, "A new house").getByLabel("Identifier").fill(`inspect_${Date.now()}`);
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
  await expect(inspector("heater_1").getByRole("heading", { name: "heater_1" })).toBeVisible();
  await inspector("heater_1").getByLabel("Power W").fill("20000");
  await inspector("heater_1").getByLabel("Power W").press("Enter");
  await expect(status).toHaveText("Set power w of heater_1.", ARRIVES);
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // A second heater placed where the first stands: an error naming both,
  // the heaters outlined on the house.
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 heater.", ARRIVES);
  await expect(errors(page)).toContainText(
    "Equipment through another item: heater_1 with heater_2.",
    ARRIVES,
  );
});

test("builder: heating pipes and a service zone placed, and changed in the inspector", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const status = page.getByTestId("builder-status");
  const items = region(page, "Items of the house");
  // The inspector of the one item chosen, under the items.
  const inspector = (item: string) =>
    region(page, "Items of the house").getByRole("region", { name: item, exact: true });
  const palette = form(page, "Place");

  await page.goto("/builder");
  await form(page, "A new house").getByLabel("Identifier").fill(`fixtures_${Date.now()}`);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // A run of heating pipes, laid along the house just above the floor.
  await palette.getByLabel("What").selectOption("pipe_run");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 pipe run.", ARRIVES);
  await expect(items.getByRole("cell", { name: "pipe run", exact: true })).toBeVisible();
  await page.getByLabel("Choose pipes_1").check();
  await expect(inspector("pipes_1").getByRole("heading", { name: "pipes_1" })).toBeVisible();
  await inspector("pipes_1").getByLabel("Count").fill("3");
  await inspector("pipes_1").getByLabel("Count").press("Enter");
  await expect(status).toHaveText("Set count of pipes_1.", ARRIVES);

  // A service zone, widened by its area's width.
  await page.getByLabel("Choose pipes_1").uncheck();
  await palette.getByLabel("What").selectOption("service_zone");
  await palette.getByRole("button", { name: "Place" }).click();
  await expect(status).toHaveText("Placed 1 service zone.", ARRIVES);
  await page.getByLabel("Choose service_zone_1").check();
  await inspector("service_zone_1").getByLabel("Area Width").fill("1.5");
  await inspector("service_zone_1").getByLabel("Area Width").press("Enter");
  await expect(status).toHaveText("Set area width of service_zone_1.", ARRIVES);
  await expect(inspector("service_zone_1").getByLabel("Area Width")).toHaveValue("1.5");
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
});

test("builder: the reference greenhouse's house edited, put back, through its file and run: the same house", async ({
  page,
}) => {
  test.setTimeout(240_000);
  const id = `reference_copy_${Date.now()}`;
  const status = page.getByTestId("builder-status");
  const runnable = page.getByTestId("builder-runnable");
  const items = bodyRows(page, "Items of the house");
  const palette = form(page, "Place");
  const give = region(page, "Rows");
  page.on("dialog", (dialog) => dialog.accept());

  await page.goto("/builder");
  const copy = form(page, "Or copy a scenario's house");
  await copy.getByLabel("Scenario").selectOption({ label: "Reference greenhouse" });
  await copy.getByLabel("The copy's identifier").fill(id);
  await copy.getByRole("button", { name: "Copy its house" }).click();
  await expect(runnable).toHaveText("It can run.", ARRIVES);
  await expect(items).toHaveCount(23);

  await test.step("a row of roof vents over two slopes, in one edit, undone in one step", async () => {
    await palette.getByLabel("What").selectOption("roof_vent");
    await palette.getByLabel("roof 1 left").check(ARRIVES);
    await palette.getByLabel("roof 2 left").check();
    await palette.getByRole("button", { name: "Place" }).click();
    await expect(status).toHaveText("Placed 4 roof vents on 2 surfaces.", ARRIVES);
    await expect(items).toHaveCount(31);
    await expect(runnable).toHaveText("It can run.", ARRIVES);
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(items).toHaveCount(23);
  });

  await test.step("the same over a slope with a vent on it: the builder names the two", async () => {
    await palette.getByLabel("roof 1 left").uncheck();
    await palette.getByLabel("roof 2 left").uncheck();
    await palette.getByLabel("roof 1 right").check();
    await palette.getByRole("button", { name: "Place" }).click();
    await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
    await expect(errors(page)).toContainText("Doors or vents overlap: roof_vent_1 with");
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(runnable).toHaveText("It can run.", ARRIVES);
  });

  await test.step("two rows given another variety cannot run, and run once put back", async () => {
    await page.getByLabel("Choose row 2").check();
    await page.getByLabel("Choose row 3").check();
    await give.getByLabel("Crop model").selectOption("organ");
    await give.getByLabel("Variety").fill("beefsteak");
    await page.getByRole("button", { name: "Give the chosen rows this crop" }).click();
    await expect(runnable).toHaveText("One error stops it running.", ARRIVES);
    await expect(errors(page)).toContainText("Rows grow different crops");
    await give.getByLabel("Variety").fill("cherry_tomato");
    await page.getByRole("button", { name: "Give the chosen rows this crop" }).click();
    await expect(runnable).toHaveText("It can run.", ARRIVES);
  });

  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download house file" }).click();
  const download = await downloading;
  const exported = await download.path();

  await test.step("its file, imported into an empty builder, is the house it was", async () => {
    await page.getByRole("button", { name: "Start again" }).click();
    await region(page, "Drafts kept")
      .locator('input[type="file"]')
      .setInputFiles({
        name: download.suggestedFilename(),
        mimeType: "application/json",
        buffer: readFileSync(exported),
      });
    await expect(status).toContainText("Imported Reference greenhouse (copy)", ARRIVES);
    await expect(runnable).toHaveText("It can run.", ARRIVES);
    await expect(items).toHaveCount(23);
    await expect(findings(page)).toHaveCount(0);
  });

  await test.step("run on a worker, its scene draws the reference greenhouse's house", async () => {
    const run = form(page, "Run it");
    await run.getByLabel("Starting on").fill("2026-03-01");
    await run.getByLabel("Days").fill("1");
    await run.getByLabel("Seed").fill("42");
    await page.getByRole("button", { name: "Save and start a run" }).click();
    await expect(page).toHaveURL(new RegExp(`/replay\\?run=${id}_r1.*follow=1`), ARRIVES);
    await expect(page.getByTestId("replay-status")).toHaveText("Finished", { timeout: 120_000 });
    const [drawn, reference] = await Promise.all(
      [`${id}_r1`, "reference_greenhouse"].map((scenario) => houseDrawn(page, scenario)),
    );
    expect(drawn?.length).toBeGreaterThan(100);
    expect(drawn).toEqual(reference);
  });
});

/**
 * What a scenario's scene draws but its plants, without the scenario's name,
 * which each entity's identifier and label start with: a plant is drawn from
 * its identifier and seed, so that a house copied under another name grows the
 * same rows of other plants.
 */
async function houseDrawn(page: Page, scenario: string): Promise<unknown[]> {
  const response = await page.request.get(`/api/scenarios/${scenario}/scene`);
  expect(response.ok()).toBe(true);
  const { entities } = JSON.parse(
    (await response.text())
      .replaceAll(scenario, "x")
      .replaceAll(scenario.replaceAll("_", " "), "x"),
  ) as { entities: { entity_id: string }[] };
  return entities
    .filter(({ entity_id }) => !/^x_plant_\d+/.test(entity_id))
    .sort((a, b) => a.entity_id.localeCompare(b.entity_id));
}

/** Each of `controls` smaller than the size it is drawn at. */
async function targetsTooSmall(controls: Locator): Promise<string[]> {
  const small: string[] = [];
  for (const control of await controls.all()) {
    const box = await control.boundingBox();
    const [name, isTarget] = await control.evaluate((element) => [
      element.textContent?.trim() || element.id,
      element.matches(".ds-button:not(.ds-button-compact), .home-button"),
    ]);
    const least = isTarget ? TARGET_PX : COMPACT_TARGET_PX;
    if ((box?.height ?? 0) < least || (box?.width ?? 0) < least) {
      small.push(`${name}: ${box?.width} by ${box?.height}`);
    }
  }
  return small;
}

test("builder: every control is a target of the size it is drawn at, at least compact", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/builder");
  await expect(page.getByRole("button", { name: "Copy its house" })).toBeVisible(ARRIVES);
  expect(await targetsTooSmall(page.locator(".builder-side").locator(CONTROLS))).toEqual([]);

  await field(page, "Identifier").fill(`e2e_targets_${Date.now()}`);
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  await form(page, "Place").getByLabel("What").selectOption("heater");
  await form(page, "Place").getByRole("button", { name: "Place" }).click();
  await page.getByLabel("Choose heater_1").check(ARRIVES);
  await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();
  expect(await targetsTooSmall(page.locator(".builder-side").locator(CONTROLS))).toEqual([]);
});

test("builder: at a phone's width the page fits its window, with the house under the forms", async ({
  page,
}) => {
  await page.setViewportSize(PHONE);
  await page.goto("/builder");
  await expect(page.getByRole("heading", { name: "A new house" })).toBeVisible();
  await expect(page.getByTestId("builder-view")).toContainText("drawn here");
  expect(await pageWidth(page)).toBe(PHONE.width);

  await field(page, "Identifier").fill(`e2e_phone_${Date.now()}`);
  await field(page, "Name").fill("The phone's house");
  await field(page, "Name").press("Enter");
  const canvas = page.getByTestId("builder-view").locator("canvas");
  await expect(canvas).toBeAttached(ARRIVES);

  expect(await pageWidth(page)).toBe(PHONE.width);
  // The house's own pane, the window's width under the forms, and all on the screen.
  await expect.poll(() => canvas.boundingBox().then((box) => box?.width)).toBe(PHONE.width);
  const drawn = await canvas.boundingBox();
  const forms = await page.locator(".builder-side").boundingBox();
  expect(drawn?.y).toBe((forms?.y ?? 0) + (forms?.height ?? 0));
  expect((drawn?.y ?? 0) + (drawn?.height ?? 0)).toBeLessThanOrEqual(PHONE.height);
});

// Where a theme is kept in this browser (`design/theme.ts`).
const THEME_KEY = "greenhouse-sim.panels";

for (const theme of ["dark", "light"] as const) {
  test(`builder: its words stand out from what they are drawn on, ${theme}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.addInitScript(({ key, chosen }) => localStorage.setItem(key, chosen), {
      key: THEME_KEY,
      chosen: theme,
    });
    const builder = page.getByRole("main");
    const palette = form(page, "Place");

    // The first step: the forms, and the note where the house is to be drawn, on a
    // pane with no ground of its own but the browser's.
    await page.goto("/builder");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(page.getByTestId("builder-view")).toContainText("drawn here");
    expect(await lowContrast(builder)).toEqual([]);

    // A house with two heaters in one place: its findings, an error among them, and
    // the two chosen, whose field to set shows a placeholder until written.
    await field(page, "Identifier").fill(`e2e_contrast_${theme}_${Date.now()}`);
    await page.getByRole("button", { name: "Draft this house" }).click();
    await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
    await palette.getByLabel("What").selectOption("heater");
    await palette.getByLabel("y (m)", { exact: true }).fill("0.6");
    await palette.getByRole("button", { name: "Place" }).click();
    await expect(page.getByLabel("Choose heater_1")).toBeVisible(ARRIVES);
    await palette.getByRole("button", { name: "Place" }).click();
    await expect(errors(page)).toBeVisible(ARRIVES);
    await page.getByLabel("Choose heater_1").check();
    await page.getByLabel("Choose heater_2").check();
    await expect(page.getByPlaceholder("power_w, base.z")).toHaveValue("");
    expect(await lowContrast(builder)).toEqual([]);
  });
}
