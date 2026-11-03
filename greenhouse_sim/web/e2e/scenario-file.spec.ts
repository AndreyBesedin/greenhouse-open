import { expect, type Page, test } from "@playwright/test";

import { BUILDER_PATH } from "../src/landing/paths";

// A scenario file the simulator has registered, opened in the setup builder
// (P17.11): the builder reads the scenario's house from the simulator, as a
// draft not saved. The file is the simulator's own download of the Climate
// box, under another identifier.

// On CI the simulator may still be working out what the spec before this
// one asked for.
const ARRIVES = { timeout: 60_000 };

async function uploadedClimateBox(page: Page, id: string): Promise<void> {
  const served = (await (await page.request.get("/api/scenarios/climate_box/file")).json()) as {
    text: string;
  };
  const document = JSON.parse(served.text) as Record<string, unknown>;
  document.greenhouse_id = id;
  document.name = "Shared box";
  // Its own words, so that the search of the start page finds no second Climate box.
  document.description = "A house sent in as a file.";
  const uploaded = await page.request.post("/api/scenarios/upload", {
    headers: { "Content-Type": "application/json" },
    data: JSON.stringify(document),
  });
  expect(uploaded.ok()).toBe(true);
}

test("an uploaded scenario opens in the builder as a draft not saved, and starts no run", async ({
  page,
}) => {
  const id = `shared_${Date.now()}`;
  await uploadedClimateBox(page, id);

  await page.goto(`${BUILDER_PATH}#scenario=${id}`);

  await expect(page.getByTestId("builder-status")).toHaveText(
    "Opened Shared box from a scenario file; not saved yet.",
    ARRIVES,
  );
  await expect(page.getByTestId("builder-draft")).toContainText(`(${id}), not saved`);
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  const kept = (await (await page.request.get("/api/runs")).json()) as { scenario_id: string }[];
  expect(kept.filter((run) => run.scenario_id === id)).toEqual([]);
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
