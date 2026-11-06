import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { BUILDER_PATH, LANDING_PATH } from "../src/landing/paths";

// A scenario file sent in from the start page (P17.11): the simulator reads it
// and registers its scenario, and the setup builder opens it as a draft not
// saved, never a run. The file is the simulator's own download of the Climate
// box, under another identifier. An installation's file, the builder's house
// file, opens there too, to be given its run's settings.

// On CI the simulator may still be working out what the spec before this
// one asked for.
const ARRIVES = { timeout: 60_000 };

const NEITHER_KIND =
  "notes.json cannot be opened: not a scenario file or a house file, which the builder's Download buttons make";

interface Picked {
  name: string;
  mimeType: string;
  buffer: Buffer;
}

/** The Climate box's file as the simulator serves it, as `change` makes it. */
async function climateBoxFile(
  page: Page,
  change: (document: Record<string, unknown>) => void,
): Promise<Picked> {
  const served = (await (await page.request.get("/api/scenarios/climate_box/file")).json()) as {
    file_name: string;
    text: string;
  };
  const document = JSON.parse(served.text) as Record<string, unknown>;
  change(document);
  return {
    name: served.file_name,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(document)),
  };
}

/** The file of a house sent in, under an identifier of its own. */
function sharedBox(page: Page, id: string): Promise<Picked> {
  return climateBoxFile(page, (document) => {
    document.greenhouse_id = id;
    document.name = "Shared box";
    // Its own words, so that the search of the start page finds no second Climate box.
    document.description = "A house sent in as a file.";
    document.duration_days = 9;
  });
}

async function keptRunsOf(page: Page, id: string): Promise<unknown[]> {
  const kept = (await (await page.request.get("/api/runs")).json()) as { scenario_id: string }[];
  return kept.filter((run) => run.scenario_id === id);
}

test("a scenario file uploaded from the start page opens in the builder, not in a run", async ({
  page,
}) => {
  const id = `shared_${Date.now()}`;
  const file = await sharedBox(page, id);

  await page.goto(LANDING_PATH);
  await page.locator(".landing-upload input[type=file]").setInputFiles(file);

  await expect(page).toHaveURL(new RegExp(`${BUILDER_PATH}#scenario=${id}$`), ARRIVES);
  await expect(page.getByTestId("builder-status")).toHaveText(
    "Opened Shared box from a scenario file; not saved yet.",
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toContainText(`(${id}), not saved`);
  // The file's run settings are the run step's.
  await expect(page.locator(".builder-run").getByLabel("Days")).toHaveValue("9");
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  // No run was started by the upload: the scenario has none kept.
  expect(await keptRunsOf(page, id)).toEqual([]);
});

test("a packaged scenario's file uploaded again is refused, next to the control", async ({
  page,
}) => {
  const file = await climateBoxFile(page, () => {});

  await page.goto(LANDING_PATH);
  await page.locator(".landing-upload input[type=file]").setInputFiles(file);

  await expect(page.getByRole("alert").filter({ hasText: "cannot be opened" })).toContainText(
    file.name,
    ARRIVES,
  );
  await expect(page).toHaveURL(/\/$/);
});

test("an uploaded scenario opens in the builder as a draft not saved, and starts no run", async ({
  page,
}) => {
  const id = `opened_${Date.now()}`;
  const file = await sharedBox(page, id);
  const uploaded = await page.request.post("/api/scenarios/upload", {
    headers: { "Content-Type": "application/json" },
    data: file.buffer.toString("utf8"),
  });
  expect(uploaded.ok()).toBe(true);

  await page.goto(`${BUILDER_PATH}#scenario=${id}`);

  await expect(page.getByTestId("builder-status")).toHaveText(
    "Opened Shared box from a scenario file; not saved yet.",
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toContainText(`(${id}), not saved`);
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  expect(await keptRunsOf(page, id)).toEqual([]);
});

/** A house drafted in the builder from its first form. */
async function draftedHouse(page: Page, id: string, rows: number): Promise<void> {
  const form = page.locator(".builder-form");
  await page.goto(BUILDER_PATH);
  await form.getByLabel("Identifier", { exact: true }).fill(id);
  await form.getByLabel("Name", { exact: true }).fill("Round trip");
  await form.getByLabel("Crop rows", { exact: true }).fill(String(rows));
  await form.getByLabel("Crop rows", { exact: true }).press("Enter");
  await expect(page.getByTestId("builder-status")).toHaveText(
    "Drafted Round trip; not saved yet.",
    ARRIVES,
  );
}

/** The house file the builder offers for the house shown. */
async function exported(page: Page): Promise<Picked> {
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download house file" }).click();
  const download = await downloading;
  return {
    name: download.suggestedFilename(),
    mimeType: "application/json",
    buffer: readFileSync(await download.path()),
  };
}

test("a house built, downloaded and uploaded from the start page opens in the builder", async ({
  page,
}) => {
  const id = `round_${Date.now()}`;
  const status = page.getByTestId("builder-status");
  await draftedHouse(page, id, 4);
  const save = page.getByRole("button", { name: "Save", exact: true });
  await save.click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  const file = await exported(page);
  expect(file.name).toBe(`${id}.house.json`);

  await page.goto(LANDING_PATH);
  await page.locator(".landing-upload input[type=file]").setInputFiles(file);

  await expect(page).toHaveURL(new RegExp(`${BUILDER_PATH}#installation=${id}$`), ARRIVES);
  // The draft it came from is kept, and is not touched: this one is not saved.
  await expect(status).toHaveText(
    `Imported Round trip from ${file.name}, a house file: it holds no run settings; not saved yet. ` +
      `A draft with the identifier ${id} is kept already: change this one's identifier to save it.`,
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toHaveText(`Round trip (${id}), not saved`);
  await expect(page.locator(".builder-rows tbody tr")).toHaveCount(4);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);
  // It is given its run's settings there.
  await expect(page.locator(".builder-run").getByLabel("Days")).toBeEditable();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);

  // Saved as it is, it is refused, and the draft stays at its revision.
  await save.click();
  await expect(status).toHaveText(
    `It is not saved: a draft with the identifier '${id}' is kept already, at revision 1: ` +
      "change this one's identifier to save it",
    ARRIVES,
  );
  const kept = (await (await page.request.get(`/api/drafts/${id}`)).json()) as {
    draft: { revision: number };
  };
  expect(kept.draft.revision).toBe(1);

  // Renamed, it is a draft of its own.
  const identity = page.locator(".builder-identity");
  await identity.getByLabel("Identifier").fill(`${id}_b`);
  await identity.getByRole("button", { name: "Rename" }).click();
  await save.click();
  await expect(status).toHaveText("Saved as revision 1.", ARRIVES);
  // No scenario was made of it on the way.
  const listed = (await (await page.request.get("/api/scenarios")).json()) as { id: string }[];
  expect(listed.map((each) => each.id)).not.toContain(id);
});

test("a house no draft holds, uploaded from the start page, is opened with nothing to rename", async ({
  page,
}) => {
  const id = `unsaved_${Date.now()}`;
  await draftedHouse(page, id, 2);
  const file = await exported(page);
  // Another tab's start page: the file is what is carried, not this tab's draft.
  const other = await page.context().newPage();

  await other.goto(LANDING_PATH);
  await other.locator(".landing-upload input[type=file]").setInputFiles(file);

  await expect(other.getByTestId("builder-status")).toHaveText(
    `Imported Round trip from ${file.name}, a house file: it holds no run settings; not saved yet.`,
    ARRIVES,
  );
  await expect(other.locator(".builder-rows tbody tr")).toHaveCount(2);
  await other.close();
});

test("a scenario file given to the builder's import opens as an upload does", async ({ page }) => {
  const id = `imported_${Date.now()}`;
  const file = await sharedBox(page, id);

  await page.goto(BUILDER_PATH);
  await page.locator(".builder-start input[type=file]").setInputFiles(file);

  await expect(page.getByTestId("builder-status")).toHaveText(
    "Opened Shared box from a scenario file; not saved yet.",
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toContainText(`(${id}), not saved`);
  await expect(page.locator(".builder-run").getByLabel("Days")).toHaveValue("9");
  expect(await keptRunsOf(page, id)).toEqual([]);
});

test("a file of neither kind is refused in plain words, on either side", async ({ page }) => {
  const file = {
    name: "notes.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ title: "My notes" })),
  };

  await page.goto(LANDING_PATH);
  await page.locator(".landing-upload input[type=file]").setInputFiles(file);
  await expect(page.getByRole("alert").filter({ hasText: "notes.json" })).toHaveText(
    NEITHER_KIND,
    ARRIVES,
  );
  await expect(page).toHaveURL(/\/$/);

  await page.goto(BUILDER_PATH);
  await page.locator(".builder-start input[type=file]").setInputFiles(file);
  await expect(page.getByTestId("builder-status")).toHaveText(NEITHER_KIND, ARRIVES);
});

test("a scenario that is not there is said not to open, and the first form is shown", async ({
  page,
}) => {
  await page.goto(`${BUILDER_PATH}#scenario=no_such_scenario`);

  await expect(page.getByTestId("builder-status")).toContainText(
    "The uploaded scenario cannot be opened:",
    ARRIVES,
  );
  await expect(page.getByRole("heading", { name: "A new house" })).toBeVisible();
});
