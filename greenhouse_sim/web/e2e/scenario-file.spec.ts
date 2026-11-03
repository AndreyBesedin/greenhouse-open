import { expect, type Page, test } from "@playwright/test";

import { BUILDER_PATH, LANDING_PATH } from "../src/landing/paths";

// A scenario file sent in from the start page (P17.11): the simulator reads it
// and registers its scenario, and the setup builder opens it as a draft not
// saved, never a run. The file is the simulator's own download of the Climate
// box, under another identifier.

// On CI the simulator may still be working out what the spec before this
// one asked for.
const ARRIVES = { timeout: 60_000 };

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
