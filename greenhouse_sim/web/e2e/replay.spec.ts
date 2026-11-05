import { expect, type Page, test } from "@playwright/test";
import { LANDING_PATH, REPLAY_PATH } from "../src/landing/paths";
import { unfold } from "./folds";

const DAY_S = 86_400;
// How long a first day of a run may take to be computed, with the other
// specs working the same simulator; a test that waits for it has twice as long.
const COMPUTES = 60_000;
const WAITS_FOR_A_DAY = COMPUTES * 2;
// How long a seek's answer is held, where a test presses keys faster than that.
const ANSWER_MS = 500;

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

// The scenario these runs are of: a slow one, so that a run is still being
// computed while it is replayed.
const SCENARIO = "solar_lab";

/** Starts a run of the scenario at a seed, through the landing page, which
 * opens its replay at the newest day, and opens that again from its start. */
async function replayOfANewRun(page: Page, seed: string): Promise<void> {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill(SCENARIO);
  await search.press("Enter");
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "New run" }).click();
  await dialog.getByLabel("Seed", { exact: true }).fill(seed);
  await dialog.getByLabel("Seconds per simulated day").fill("1");
  await dialog.getByRole("button", { name: "Start run" }).click();
  await expect(page).toHaveURL(new RegExp(`${REPLAY_PATH}\\?run=.*&follow=1$`));
  await page.goto(page.url().replace("&follow=1", ""));
}

test("a stored run is replayed: its header, its scene and a timeline over what is computed", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY);
  await replayOfANewRun(page, "41");
  // What the landing page asked on its way is its own; the replay's is counted.
  const errors = collectErrors(page);

  await expect(page.getByTestId("replay-subtitle")).toHaveText(/^seed 41 · epoch \d+ · /);
  await expect(page.getByTestId("replay-status")).toHaveText(/Queued|Running|Finished/);
  await expect(page.locator("canvas")).toBeVisible();
  // One way home, not two: the house, and no back link besides.
  await expect(page.getByRole("link", { name: "Home" })).toHaveCount(1);
  await expect(page.getByRole("link", { name: "Scenarios" })).toHaveCount(0);
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 00:00");
  expect(errors).toEqual([]);

  // The timeline reaches as far as the run is computed, a day at a time.
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), { timeout: COMPUTES })
    .toBeGreaterThanOrEqual(DAY_S);

  // A key moves the handle a day on, and the scene follows to that moment.
  await handle.focus();
  await page.keyboard.press("PageUp");
  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 24:00");
  await expect(page.getByTestId("replay-moment")).toHaveText("Day 1, 24:00");
  await expect(page.getByTestId("scene-status")).toContainText("solar_lab, day 1,");

  // The next day button does the same from the start.
  await page.keyboard.press("Home");
  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 00:00");
  await page.locator(".replay-transport").getByRole("button", { name: "Next day" }).click();
  await expect(page.getByTestId("replay-moment")).toHaveText("Day 1, 24:00");

  // One thing moves the moment: the viewer's own climate controls stand aside.
  await expect(page.getByTestId("climate-followed")).toContainText("replay's timeline");
  await expect(page.locator('fieldset[aria-label="Climate run"] button')).toHaveCount(0);
});

test("a replay plays on its own pace, and pauses", async ({ page }) => {
  test.setTimeout(WAITS_FOR_A_DAY);
  await replayOfANewRun(page, "42");
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), { timeout: COMPUTES })
    .toBeGreaterThanOrEqual(DAY_S);

  // The transport's own controls: the viewer's panels have a Play and a Pace of their own.
  const transport = page.locator(".replay-transport");
  await transport.getByLabel("Pace").selectOption("2");
  await transport.getByRole("button", { name: "Play" }).click();
  await expect(transport.getByRole("button", { name: "Pause" })).toBeVisible();
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuenow")), { timeout: COMPUTES })
    .toBeGreaterThan(0);
  await transport.getByRole("button", { name: "Pause" }).click();
  await expect(transport.getByRole("button", { name: "Play" })).toBeVisible();
});

test("a run that is being computed can be followed at its newest day", async ({ page }) => {
  await replayOfANewRun(page, "43");

  const follow = page.getByRole("button", { name: "Follow the newest day" });
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
});

test("keys pressed faster than the answers move from the moment last sought", async ({ page }) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  await replayOfANewRun(page, "48");
  const handle = page.getByRole("slider", { name: "Position in the run" });
  const moment = page.getByTestId("replay-moment");
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), {
      timeout: WAITS_FOR_A_DAY,
    })
    .toBeGreaterThanOrEqual(2 * DAY_S);
  await handle.focus();
  await page.keyboard.press("PageUp");
  await expect(moment).toHaveText("Day 1, 24:00");
  await page.keyboard.press("PageUp");
  await expect(moment).toHaveText("Day 2, 24:00");

  // Every answer now comes later than the next key.
  const sought: (string | null)[] = [];
  await page.route("**/seek*", async (route) => {
    sought.push(new URL(route.request().url()).searchParams.get("t"));
    await new Promise((answered) => setTimeout(answered, ANSWER_MS));
    await route.continue();
  });
  await page.keyboard.press("Home");
  await page.keyboard.press("PageUp");

  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 24:00");
  await expect(moment).toHaveText("Day 1, 24:00");
  expect(sought.at(-1)).toBe(String(DAY_S));
});

test("a panel's fork names the moment it takes while the climate field is on its way", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY);
  await replayOfANewRun(page, "46");
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), { timeout: COMPUTES })
    .toBeGreaterThanOrEqual(DAY_S);
  const fork = page.getByTestId("fork-levels").getByRole("button").first();
  await expect(fork).toHaveText("Fork from here with these levels", { timeout: COMPUTES });

  let answer = () => {};
  const answered = new Promise<void>((resolve) => {
    answer = resolve;
  });
  await page.route("**/fields/climate*", async (route) => {
    await answered;
    await route.continue();
  });
  await handle.focus();
  await page.keyboard.press("PageUp");
  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 24:00");
  await expect(fork).toHaveText("Fork from Day 1, 00:00 with these levels");

  answer();
  await expect(fork).toHaveText("Fork from here with these levels", { timeout: COMPUTES });
});

test("a stored run is forked from the moment shown, and stays there to go back to", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  await replayOfANewRun(page, "45");
  const parent = page.url();
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), { timeout: COMPUTES })
    .toBeGreaterThanOrEqual(DAY_S);
  await handle.focus();
  await page.keyboard.press("PageUp");
  await expect(page.getByTestId("replay-moment")).toHaveText("Day 1, 24:00");

  await page.getByTestId("replay-fork").click();
  await expect(page.getByTestId("fork-question")).toContainText("beside the others");
  await expect(page).toHaveURL(parent);
  await page.getByRole("button", { name: "Make the fork" }).click();

  // A new epoch, at an address of its own, naming where it comes from.
  await expect(page).not.toHaveURL(parent);
  await expect(page.getByTestId("replay-subtitle")).toContainText(
    /forked from epoch \d+ at Day 1, 24:00/,
  );
  await expect(page.getByTestId("replay-moment")).toHaveText("Day 1, 24:00");
  await expect(page.locator("canvas")).toBeVisible();
  // What cannot be a fork says why, rather than drawing another run.
  await expect(page.getByTestId("replayed-weather")).toContainText("keeps the weather");

  await page.getByRole("link", { name: "The run it came from" }).click();
  await expect(page).toHaveURL(parent);
  await expect(page.getByTestId("replay-subtitle")).not.toContainText("forked");
});

test("a level set in a replay is read beside what the run has, until it is put back", async ({
  page,
}) => {
  await replayOfANewRun(page, "47");
  await unfold(page, "Equipment");
  const reading = page.getByTestId("equipment-heater");
  const slider = page.getByRole("slider", { name: "heater level" });
  await expect(reading).toHaveText("off");

  await slider.fill("100");

  await expect(slider).toHaveValue("100");
  await expect(reading).toHaveText("off, set to 100%");
  await expect(page.getByTestId("equipment-summary")).toHaveText("Equipment: all off");

  await page.getByRole("button", { name: "Put them back" }).click();
  await expect(slider).toHaveValue("0");
  await expect(reading).toHaveText("off");
});

test("an address that names no run, or a run that is not kept, says so and offers the way home", async ({
  page,
}) => {
  await page.goto(REPLAY_PATH);
  await expect(page.getByText("names no run to replay")).toBeVisible();
  await expect(page.getByRole("link", { name: "Home" })).toBeVisible();

  await page.goto(`${REPLAY_PATH}?run=there-is-no-such-run&epoch=0`);
  await expect(page.getByTestId("replay-notice")).toContainText("cannot be replayed");
  await page.getByRole("link", { name: "Home" }).click();
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
});

test("a replay's other runs are the scenario's, on the landing page", async ({ page }) => {
  await replayOfANewRun(page, "44");

  await page.getByRole("link", { name: "Other runs" }).click();

  await expect(page).toHaveURL(/#runs=solar_lab$/);
  await expect(page.getByRole("dialog").getByRole("heading")).toContainText("Solar");
});
