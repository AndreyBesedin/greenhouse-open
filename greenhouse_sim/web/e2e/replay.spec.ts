import { expect, type Page, test } from "@playwright/test";
import { LANDING_PATH, REPLAY_PATH, runsAddress } from "../src/landing/paths";
import { unfold } from "./folds";
import { askForRun, computedTo, openReplay } from "./replays";

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

/** Starts a run of a scenario at a seed and a pace, through the landing page,
 * which opens its replay at the newest day, and opens that again from its
 * start. By default a run of `SCENARIO` at a second a day; an empty pace is as
 * fast as it computes. */
async function replayOfANewRun(
  page: Page,
  seed: string,
  { scenario = SCENARIO, pace = "1" }: { scenario?: string; pace?: string } = {},
): Promise<void> {
  await page.goto(LANDING_PATH);
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.fill(scenario);
  await search.press("Enter");
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "New run" }).click();
  await dialog.getByLabel("Seed", { exact: true }).fill(seed);
  await dialog.getByLabel("Seconds per simulated day").fill(pace);
  await dialog.getByRole("button", { name: "Start run" }).click();
  await expect(page).toHaveURL(new RegExp(`${REPLAY_PATH}\\?run=.*&follow=1$`));
  await page.goto(page.url().replace("&follow=1", ""));
}

/** Stops the run the page replays, through the simulator's API, as the start
 * page's Stop does: it is interrupted with what it committed, and its replay
 * says so. A run that is computed no longer is changed by a fork (P22.1). */
async function stopReplayed(page: Page): Promise<void> {
  const replayed = new URL(page.url()).searchParams;
  const run = encodeURIComponent(replayed.get("run") ?? "");
  const stopped = await page.request.post(`/api/runs/${run}/epochs/${replayed.get("epoch")}/stop`);
  expect(stopped.ok()).toBe(true);
  await expect(page.getByTestId("replay-status")).toHaveText("Interrupted", { timeout: COMPUTES });
}

/** The moment a replay says the run took a change from, in seconds into it. */
function momentTaken(said: string): number {
  const [, day, hours, minutes] = /from Day (\d+), (\d\d):(\d\d)\.$/.exec(said) ?? [];
  return (Number(day) - 1) * DAY_S + Number(hours) * 3600 + Number(minutes) * 60;
}

/** The changes and forks the page asks of the simulator, as it asks them. */
function changesAndForks(page: Page): string[] {
  const asked: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && /\/epochs\/\d+\/(changes|forks)$/.test(path)) {
      asked.push(path.replace(/.*\//, ""));
    }
  });
  return asked;
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
  await expect(page.getByTestId("scene-status")).toContainText("solar_lab, 1 day in,");

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

test("a run being computed is watched from its list in the replay: at its newest day, and Play moves on as days arrive", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  await replayOfANewRun(page, "43");
  const replayed = page.url();
  try {
    // One way to watch it in its list (P22.2): its replay, which opens following.
    await page.goto(runsAddress(SCENARIO));
    const row = page
      .getByRole("dialog")
      .locator(".landing-run")
      .filter({ hasText: /Seed 43(?!\d)/ })
      .first();
    await expect(row.getByRole("link")).toHaveCount(1);
    await row.getByRole("link", { name: /^Replay the run with seed 43,/ }).click();
    await expect(page).toHaveURL(new RegExp(`${REPLAY_PATH}\\?run=.*&follow=1$`));

    const follow = page.getByRole("button", { name: "Follow the newest day" });
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    // Following, the handle stands at the frontier as the run computes on.
    const handle = page.getByRole("slider", { name: "Position in the run" });
    await expect
      .poll(async () => Number(await handle.getAttribute("aria-valuenow")), {
        timeout: WAITS_FOR_A_DAY,
      })
      .toBeGreaterThanOrEqual(DAY_S);
    const [followedTo, frontier] = await handle.evaluate((slider) => [
      Number(slider.getAttribute("aria-valuenow")),
      Number(slider.getAttribute("aria-valuemax")),
    ]);
    expect(followedTo).toBe(frontier);

    // Played from the frontier, it waits there, and moves on as days arrive.
    const transport = page.locator(".replay-transport");
    await transport.getByLabel("Pace").selectOption("2");
    await transport.getByRole("button", { name: "Play" }).click();
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await expect(transport.getByRole("button", { name: "Pause" })).toBeVisible();
    await expect
      .poll(async () => Number(await handle.getAttribute("aria-valuenow")), {
        timeout: WAITS_FOR_A_DAY,
      })
      .toBeGreaterThan(followedTo);
  } finally {
    const started = new URL(replayed).searchParams;
    await page.request.post(
      `/api/runs/${encodeURIComponent(started.get("run") ?? "")}/epochs/${started.get("epoch")}/stop`,
    );
  }
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
  // A run still computed is steered from its panels, not forked (P22.1).
  await stopReplayed(page);
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
  await stopReplayed(page);
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

test("a target set in the replay of a run being computed steers it from its moment, and nothing forks", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  // Paced, so that it is still computed when the change is asked.
  await replayOfANewRun(page, "51", { scenario: "reference_greenhouse", pace: "20" });
  const replayed = page.url();
  const asked = changesAndForks(page);
  await expect(page.getByTestId("replay-status")).toHaveText(/Queued|Running/);
  const steering = page.getByTestId("epoch-steering");
  await expect(steering).toContainText("nothing forks");
  await expect(page.getByTestId("fork-levels")).toHaveCount(0);
  const summary = page.getByTestId("targets-summary");
  await expect(summary).toHaveText("Heating targets: 18 °C by day, 16 °C by night", {
    timeout: COMPUTES,
  });

  await unfold(page, "Heating targets");
  const targets = page.locator("details.targets-fold");
  await targets.getByLabel("By day, °C").fill("24");
  await targets.getByRole("button", { name: "Set from the run's next minute" }).click();

  // Asked of the epoch, taken by its worker at its own clock, and no fork.
  const status = page.getByTestId("epoch-steering-status");
  await expect(status).toHaveText(/^The run took the latest change from Day \d+, \d\d:\d\d\.$/, {
    timeout: COMPUTES,
  });
  const takenS = momentTaken((await status.textContent()) ?? "");
  expect(asked).toEqual(["changes"]);
  await expect(page.getByTestId("fork-question")).toHaveCount(0);
  await expect(page).toHaveURL(replayed);
  // The moment shown is before it: the run had 18 °C by day then.
  await expect(summary).toHaveText("Heating targets: 18 °C by day, 16 °C by night");

  // Once the run is computed past the moment, the replay shows it there.
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuemax")), {
      timeout: WAITS_FOR_A_DAY,
    })
    .toBeGreaterThan(takenS);
  await handle.focus();
  await page.keyboard.press("End");
  await expect(summary).toHaveText("Heating targets: 24 °C by day, 16 °C by night", {
    timeout: COMPUTES,
  });
  expect(asked).toEqual(["changes"]);
  await stopReplayed(page);
});

test("a level set in the replay of a finished run forks it", async ({ page }) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  // As fast as it computes, so that it has finished when the level is set.
  await replayOfANewRun(page, "52", { scenario: "climate_box", pace: "" });
  const parent = page.url();
  const asked = changesAndForks(page);
  await expect(page.getByTestId("replay-status")).toHaveText("Finished", {
    timeout: WAITS_FOR_A_DAY,
  });
  await expect(page.getByTestId("epoch-steering")).toHaveCount(0);

  await unfold(page, "Equipment");
  await page.getByRole("slider", { name: "heater level" }).fill("100");
  await page.getByRole("button", { name: "Fork from here with these levels" }).click();
  await page.getByRole("button", { name: "Make the fork" }).click();

  await expect(page).not.toHaveURL(parent);
  await expect(page.getByTestId("replay-subtitle")).toContainText(
    /forked from epoch \d+ at Day 1, 00:00/,
  );
  expect(asked).toEqual(["forks"]);
});

test("a moment whose field fails does not stop the replay playing on", async ({ page }) => {
  test.setTimeout(WAITS_FOR_A_DAY * 2);
  const run = await askForRun(page, "climate_box", { seed: 67 });
  await computedTo(page, run, 3 * DAY_S, WAITS_FOR_A_DAY);
  // Every climate field asked for after the first fails; the moments asked, by
  // the seconds into the run each names.
  const moments = new Set<string>();
  await page.route("**/api/scenarios/climate_box/fields/climate*", (route) => {
    const first = moments.size === 0;
    moments.add(new URL(route.request().url()).searchParams.get("t") ?? "0");
    return first
      ? route.continue()
      : route.fulfill({ status: 500, json: { error: "a failure for the test" } });
  });
  await openReplay(page, run);

  // Played, the moment drawn moves on past each that fails, and again.
  const transport = page.locator(".replay-transport");
  await transport.getByLabel("Pace").selectOption("2");
  await transport.getByRole("button", { name: "Play" }).click();
  await expect.poll(() => moments.size, { timeout: COMPUTES }).toBeGreaterThan(3);
  await expect(page.getByTestId("climate-failed")).toContainText("cannot be drawn");
});

test("the replay of a house without equipment draws its climate, nothing refused", async ({
  page,
}) => {
  test.setTimeout(WAITS_FOR_A_DAY);
  const refused: string[] = [];
  page.on("response", (response) => {
    if (response.status() === 404 && /\/(fields\/climate|climate\/)/.test(response.url())) {
      refused.push(response.url());
    }
  });
  const run = await askForRun(page, "airflow_box", { seed: 68 });
  await openReplay(page, run);

  await expect(page.getByTestId("field-status")).toContainText("airflow_box_climate", {
    timeout: COMPUTES,
  });
  await expect(page.getByTestId("main-view")).not.toHaveAttribute("data-light", "fixed");
  await expect(page.getByTestId("climate-failed")).toHaveCount(0);
  expect(refused).toEqual([]);
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
