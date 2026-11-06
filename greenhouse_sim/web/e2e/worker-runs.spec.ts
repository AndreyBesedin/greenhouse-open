import { expect, type Locator, type Page, test } from "@playwright/test";
import { LANDING_PATH, REPLAY_PATH, replayTarget, runsAddress } from "../src/landing/paths";

// A scenario whose run takes long enough, at this pace, to be seen computing:
// the two started here overlap by far, and are stopped before they end.
const SCENARIO = "solar_lab";
const SECONDS_PER_DAY = "20";
// A worker is a process started from nothing, which then computes its first day.
const WORKS = { timeout: 90_000 };

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

/** Starts a run from the dialog the page has open, and waits for its replay. */
async function start(page: Page, seed: string): Promise<{ runId: string; epoch: number }> {
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "New run" }).click();
  await dialog.getByLabel("Seed", { exact: true }).fill(seed);
  await dialog.getByLabel("Seconds per simulated day").fill(SECONDS_PER_DAY);
  await dialog.getByRole("button", { name: "Start run" }).click();
  await expect(page).toHaveURL(new RegExp(`${REPLAY_PATH}\\?run=.*&follow=1$`));
  const target = replayTarget(new URL(page.url()).search);
  if (target === null) {
    throw new Error(`no run in ${page.url()}`);
  }
  return target;
}

function rowOf(within: Page | Locator, seed: string): Locator {
  return within
    .locator(".landing-run")
    .filter({ hasText: new RegExp(`seed ${seed}(?!\\d)`, "i") })
    .first();
}

/** How many days a row says are computed. */
async function daysIn(row: Locator): Promise<number> {
  const text = await row.locator(".landing-run-progress span").textContent();
  return Number(/^(\d+)/.exec(text ?? "")?.[1]);
}

// What earlier specs left computing would hold the workers these wait for.
test.beforeEach(async ({ page }) => {
  const runs: { run_id: string; epoch: number; status: string }[] = await (
    await page.request.get("/api/runs")
  ).json();
  for (const { run_id, epoch, status } of runs) {
    if (status === "queued" || status === "running") {
      await page.request.post(`/api/runs/${encodeURIComponent(run_id)}/epochs/${epoch}/stop`);
    }
  }
});

test("two runs of one scenario are computed at once, from the dialog, each followed in its replay", async ({
  page,
}) => {
  test.setTimeout(360_000);
  const started: { runId: string; epoch: number }[] = [];
  try {
    await page.goto(runsAddress(SCENARIO));
    started.push(await start(page, "71"));

    // Start lands in the replay, following the newest day, from the first answer.
    const follow = page.getByRole("button", { name: "Follow the newest day" });
    await expect(follow).toHaveAttribute("aria-pressed", "true", WORKS);
    await expect(page.getByTestId("replay-subtitle")).toContainText("seed 71");
    const computed = page.getByRole("slider", { name: "Position in the run" });
    await expect
      .poll(async () => Number(await computed.getAttribute("aria-valuenow")), WORKS)
      .toBeGreaterThan(0);

    // The second is asked for from the replay's way to the others.
    await page.getByRole("link", { name: "Other runs" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    started.push(await start(page, "72"));

    // Both are computing, on the page and in the dialog, moving on with no reload.
    const errors = collectErrors(page);
    await page.goto(LANDING_PATH);
    const first = rowOf(page, "71");
    const second = rowOf(page, "72");
    await expect(first).toContainText("Running", WORKS);
    await expect(second).toContainText("Running", WORKS);
    const firstDays = await daysIn(first);
    await expect.poll(() => daysIn(first), WORKS).toBeGreaterThan(firstDays);
    await expect(second).toContainText("Running");
    // Both workers a simulator runs by default are busy, as the page says.
    await expect(page.getByTestId("landing-room")).toContainText("Workers2 of 2 busy");

    // A fragment alone would not load the page again.
    await page.goto("about:blank");
    await page.goto(runsAddress(SCENARIO));
    const dialog = page.getByRole("dialog");
    const inDialog = rowOf(dialog, "72");
    await expect(inDialog).toContainText("Running", WORKS);
    const dialogDays = await daysIn(inDialog);
    await expect.poll(() => daysIn(inDialog), WORKS).toBeGreaterThan(dialogDays);
    await expect(inDialog.getByRole("link", { name: "Follow" })).toHaveAttribute(
      "href",
      /\/replay\?.*&follow=1$/,
    );
    // No playback was asked after: a worker's scenario has none, and asking
    // would be a 404 each time the runs are.
    expect(errors).toEqual([]);
  } finally {
    for (const { runId, epoch } of started) {
      await page.request.post(`/api/runs/${encodeURIComponent(runId)}/epochs/${epoch}/stop`);
    }
  }
});

test("a run is stopped with what it computed, resumed as the same epoch, and deleted once stopped", async ({
  page,
}) => {
  test.setTimeout(360_000);
  const seed = "73";
  await page.goto(runsAddress(SCENARIO));
  const started = await start(page, seed);
  await page.goto("about:blank");
  await page.goto(runsAddress(SCENARIO));
  const dialog = page.getByRole("dialog");
  const row = rowOf(dialog, seed);
  const stop = row.getByRole("button", { name: `Stop the run with seed ${seed}` });
  const resume = row.getByRole("button", { name: `Resume the run with seed ${seed}` });
  try {
    await expect(row).toContainText("Running", WORKS);
    await expect.poll(() => daysIn(row), WORKS).toBeGreaterThan(0);

    // Deleting it now says which, and what to do, in words, with the control there.
    await row.getByRole("button", { name: /^Delete the run with seed/ }).click();
    await row.getByRole("button", { name: /^Delete the run with seed/ }).click();
    const refused = dialog.getByRole("alert");
    await expect(refused).toContainText(`seed ${seed}, epoch ${started.epoch}`);
    await expect(refused).toContainText("stop it, then delete it");
    await expect(refused).not.toContainText(started.runId);

    await stop.click();
    await expect(row).toContainText("Interrupted", WORKS);
    await expect(stop).toHaveCount(0);
    const kept = await daysIn(row);
    expect(kept).toBeGreaterThan(0);
    // What its worker used, as far as its last commit: measured, not "not measured".
    const used = row.locator(".landing-run-usage");
    await expect(used).toContainText(/CPU\d/);
    await expect(used).toContainText(/Peak memory[\d.]+ MB/);
    await expect(used).toContainText(/Wall time\d/);
    await expect(used).toContainText(/Computed\d+ days?/);

    // The same epoch, from what it had: not from its first day.
    await resume.click();
    await expect(row).toContainText(`epoch ${started.epoch}`);
    await expect(row).toContainText(/Queued|Running/, WORKS);
    expect(await daysIn(row)).toBeGreaterThanOrEqual(kept);
    await expect.poll(() => daysIn(row), WORKS).toBeGreaterThan(kept);

    await stop.click();
    await expect(row).toContainText("Interrupted", WORKS);
    await row.getByRole("button", { name: /^Delete the run with seed/ }).click();
    await row.getByRole("button", { name: /^Delete the run with seed/ }).click();
    await expect(row).toHaveCount(0);
    // The keyboard is left in the dialog, on its heading, not on the page's body.
    await expect(dialog.getByRole("heading", { level: 2 })).toBeFocused();
  } finally {
    await page.request.post(
      `/api/runs/${encodeURIComponent(started.runId)}/epochs/${started.epoch}/stop`,
    );
  }
});

test("an uploaded scenario is run, stopped and resumed by a worker too", async ({ page }) => {
  test.setTimeout(360_000);
  const id = `built_${Date.now()}`;
  const file = await page.request.get("/api/scenarios/sensor_lab/file");
  const scenario = JSON.parse((await file.json()).text);
  scenario.greenhouse_id = id;
  scenario.name = `Built ${id}`;
  scenario.installation.installation_id = id;
  const uploaded = await page.request.post("/api/scenarios/upload", {
    data: JSON.stringify(scenario),
    headers: { "Content-Type": "application/json" },
  });
  expect(uploaded.ok()).toBe(true);

  await page.goto(`/#runs=${id}`);
  const started = await start(page, "74");
  try {
    await page.goto("about:blank");
    await page.goto(`/#runs=${id}`);
    const dialog = page.getByRole("dialog");
    const row = rowOf(dialog, "74");
    await expect(row).toContainText("Running", WORKS);
    await expect.poll(() => daysIn(row), WORKS).toBeGreaterThan(0);
    await expect(row).not.toContainText("Failed");

    await row.getByRole("button", { name: /^Stop the run/ }).click();
    await expect(row).toContainText("Interrupted", WORKS);
    const kept = await daysIn(row);
    await row.getByRole("button", { name: /^Resume the run/ }).click();
    await expect.poll(() => daysIn(row), WORKS).toBeGreaterThan(kept);
    await expect(row).not.toContainText("Failed");
  } finally {
    await page.request.post(
      `/api/runs/${encodeURIComponent(started.runId)}/epochs/${started.epoch}/stop`,
    );
  }
});
