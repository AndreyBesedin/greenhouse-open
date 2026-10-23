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
