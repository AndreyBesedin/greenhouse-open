import { expect, type Locator, type Page, test } from "@playwright/test";
import {
  LANDING_PATH,
  REPOSITORY_URL,
  replayTarget,
  runsAddress,
  VIEWER_PATH,
} from "../src/landing/paths";
import type { StoredRun } from "../src/landing/storedRuns";
import { answerAsTheSimulator, RUN, SCENARIO_ID } from "./visual/pageAnswers";

// Just over the width at which a list's rows wrap (`styles.css`).
const NARROWEST_WITH_COLUMNS = 860;

/** Where each of a list's rows draws what `selector` finds of it: its left edge
 * and width, to the pixel, for those that have one. */
async function columnOf(rows: Locator, selector: string): Promise<string[]> {
  const found: string[] = [];
  for (const row of await rows.all()) {
    const part = row.locator(selector);
    if ((await part.count()) > 0) {
      const box = await part.boundingBox();
      found.push(`${Math.round(box?.x ?? 0)}+${Math.round(box?.width ?? 0)}`);
    }
  }
  return found;
}

/** Everything the page reports as an error, so a test can insist on none. */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  return errors;
}

test("a list's rows line up, and a dialog's controls stay on their row, whatever each row has", async ({
  page,
}) => {
  const runs: StoredRun[] = [
    RUN,
    { ...RUN, epoch: 1, status: "running", progress: 0.25 },
    { ...RUN, epoch: 2, status: "interrupted", progress: 0.5 },
  ];
  await answerAsTheSimulator(page);
  await page.route(/\/api\/(runs|scenarios\/[^/]+\/runs)$/, (route) =>
    route.fulfill({ json: runs }),
  );
  const expectColumns = async (rows: Locator) => {
    await expect(rows).toHaveCount(runs.length);
    // One x and one width in each column: the bars, and each kind of control.
    for (const [selector, rowsWithIt] of [
      ["progress", 3],
      [".landing-status", 3],
      [".landing-run-replay", 3],
      [".landing-run-follow", 1],
      [".landing-run-control", 2],
      [".landing-run-delete", 3],
    ] as const) {
      const column = await columnOf(rows, selector);
      expect(column).toHaveLength(rowsWithIt);
      if (selector !== ".landing-status") {
        expect(new Set(column).size, `${selector}: ${column.join(", ")}`).toBe(1);
      }
    }
  };

  await page.goto(LANDING_PATH);
  await expectColumns(page.locator(".landing-run"));

  await page.goto("about:blank");
  await page.goto(runsAddress(SCENARIO_ID));
  const rows = page.getByRole("dialog").locator(".landing-run");
  await expectColumns(rows);
  // Replay and Follow beside Stop and Delete, not above them, down to the width
  // the rows give way at.
  await page.setViewportSize({ width: NARROWEST_WITH_COLUMNS, height: 800 });
  const running = rows.nth(1);
  const tops = await Promise.all(
    [
      ".landing-run-replay",
      ".landing-run-follow",
      ".landing-run-control",
      ".landing-run-delete",
    ].map(async (selector) => (await running.locator(selector).boundingBox())?.y),
  );
  expect(new Set(tops).size, `the tops of a row's controls: ${tops.join(", ")}`).toBe(1);
});

test("the bare address is the page where a person decides what to do", async ({ page }) => {
  const errors = collectErrors(page);

  await page.goto(LANDING_PATH);

  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  const contribute = page.getByRole("link", { name: "Contribute" });
  await expect(contribute).toHaveAttribute("href", REPOSITORY_URL);
  await expect(contribute).toHaveAttribute("target", "_blank");
  await expect(contribute).toHaveAttribute("rel", /noopener/);
  await expect(page.getByRole("link", { name: "Open the builder" })).toHaveAttribute(
    "href",
    "/builder",
  );
  // The runs kept are told, with what their objects hold, or that none is
  // kept (the specs share a simulator, so which of the two is not asked).
  await expect(
    page.getByText(/No run has been kept yet|\d+ runs? kept, [\d.]+ (B|kB|MB)/),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("a scenario is searched for and opened in the viewer", async ({ page }) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });

  await search.click();
  await expect(page.getByRole("option", { name: /Climate box/ })).toBeVisible();
  await search.fill("climate_box");
  await expect(page.getByRole("option")).toHaveCount(2);
  await search.press("Enter");

  // The scenario's runs are in a dialog, from which the viewer opens on it.
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toContainText("Climate box");
  await dialog.getByRole("link", { name: "Open in the viewer" }).click();

  await expect(page).toHaveURL(/\/view\?scenario=climate_box$/);
  await expect(page.locator("canvas")).toBeVisible();
});

test("a search offers first the scenarios it names, before those it is only a word of", async ({
  page,
}) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });

  // "tom" is in the reference greenhouse's description, and two scenarios' names.
  await search.fill("tom");
  const options = page.getByRole("option");
  await expect(options.nth(0)).toContainText(/Tomato compartment|TOMGRO house/);
  await expect(options.nth(1)).toContainText(/Tomato compartment|TOMGRO house/);
  await search.press("Enter");
  await expect(page.getByRole("dialog").getByRole("heading", { level: 2 })).toContainText(
    /Tomato compartment|TOMGRO house/,
  );
});

test("the viewer is at its own address, and an address with a query is still the viewer", async ({
  page,
}) => {
  // A page loaded directly at a path below the root, and the links made
  // before the landing page existed.
  await page.goto(VIEWER_PATH);
  await expect(page.getByRole("heading", { name: "greenhouse-sim viewer" })).toBeVisible();

  await page.goto("/?scenario=climate_box");
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0");
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toHaveCount(0);
});

test("a dialog closed by its button gives focus back to the search, with its list shut", async ({
  page,
}) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill("climate_box");
  await search.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toContainText("Climate box");

  await dialog.getByRole("button", { name: "Close" }).click();

  await expect(dialog).toHaveCount(0);
  await expect(search).toBeFocused();
  await expect(page.getByRole("option")).toHaveCount(0);
});

test("a dialog closed by Escape gives focus back to the search, with its list shut", async ({
  page,
}) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill("climate_box");
  await search.press("Enter");
  await expect(page.getByRole("dialog").getByRole("heading")).toContainText("Climate box");

  await page.keyboard.press("Escape");

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(search).toBeFocused();
  await expect(page.getByRole("option")).toHaveCount(0);
  // Asked for, it opens as ever.
  await search.click();
  await expect(page.getByRole("option").first()).toBeVisible();
});

test("a run is started at a seed from a scenario's dialog, listed, and not removed while it computes", async ({
  page,
}) => {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill("solar_lab");
  await search.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toContainText("Solar");

  await dialog.getByRole("button", { name: "New run" }).click();
  // Exactly: the runs of the scenario that other specs have started have labels that say a seed.
  await dialog.getByLabel("Seed", { exact: true }).fill("7");
  // Long enough not to end while this looks at it; it is stopped at the end.
  await dialog.getByLabel("Seconds per simulated day").fill("10");
  await dialog.getByRole("button", { name: "Start run" }).click();

  await expect(page).toHaveURL(/\/replay\?run=.*&follow=1$/);
  const started = replayTarget(new URL(page.url()).search);
  try {
    await page.goto(runsAddress("solar_lab"));
    const row = dialog
      .locator(".landing-run")
      .filter({ hasText: /Seed 7(?!\d)/ })
      .first();
    await expect(row).toBeVisible();
    // The seed whole, and the row's own: other specs leave runs at other seeds.
    await row.getByRole("button", { name: /^Delete the run with seed 7,/ }).click();
    await row.getByRole("button", { name: /^Delete the run with seed 7,/ }).click();
    await expect(dialog.getByRole("alert")).toContainText("being computed");
    await expect(row).toBeVisible();

    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  } finally {
    await page.request.post(
      `/api/runs/${encodeURIComponent(started?.runId ?? "")}/epochs/${started?.epoch}/stop`,
    );
  }
});
