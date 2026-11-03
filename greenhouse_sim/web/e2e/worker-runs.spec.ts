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
    .filter({ hasText: new RegExp(`seed ${seed}\\b`, "i") })
    .first();
}

/** How many days a row says are computed. */
async function daysIn(row: Locator): Promise<number> {
  const text = await row.locator(".landing-run-progress span").textContent();
  return Number(/^(\d+)/.exec(text ?? "")?.[1]);
}

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

test("a scenario no worker can run starts by its playback, and says where to follow it", async ({
  page,
}) => {
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

  await page.goto(`/#run=${id}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("replaces the one now playing")).toBeVisible();
  await dialog.getByRole("button", { name: "Start run" }).click();

  // The page stays, the run is computing, and it has not failed for want of a worker.
  await expect(dialog.getByRole("link", { name: "Follow it in the viewer" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`#run=${id}$`));
  const row = dialog.locator(".landing-run").first();
  await expect(row).toContainText(/Running/, WORKS);
  await expect.poll(() => daysIn(row), WORKS).toBeGreaterThan(0);
  await expect(row).not.toContainText("Failed");
});
