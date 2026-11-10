import { type APIRequestContext, expect, type Page, test } from "@playwright/test";
import { dayCount } from "../src/clock.ts";
import { BUILDER_PATH, LANDING_PATH, replayTarget, VIEWER_PATH } from "../src/landing/paths";
import { caption, linger, markOpening, say } from "./demoSteps";
import { unfold } from "./folds";

// The README's video: the main features, under a minute at the speed
// `uv run record-demo` cuts it at (tools/greenhouse_dev/demo_video.py), each
// under a caption, for someone who has never seen them. Recorded
// (playwright.demo.config.ts), it lingers for DEMO_PAUSE_MS a step, on a store
// of its own. As a browser test it lingers on nothing and it checks that each
// step still shows what its caption names.
//
// The replay it shows is of a run a worker computed before the video begins:
// DEMO_DAYS of it, which take a worker about 7 s each, so that the video waits
// on no worker and the crop has grown. A browser test makes do with two days.

const SCENARIO = "reference_greenhouse";
const DAYS = Number(process.env.DEMO_DAYS ?? 2);
const RUN_DAYS = 120;
const DAY_TAKES_AT_MOST_MS = 60_000;
const ARRIVES = { timeout: 180_000 };
// The camera on the whole house, from south-west of it and above, with the
// panels folded out of its way.
const ON_THE_HOUSE = "-5.5:-12.5:9.5,5:4.8:1.5";
// Noon of the day its kept checkpoint opens on, its first with a red fruit.
const OPENING_S = (86 + 0.5) * 86_400;
const OPENING_MOMENT = "day 87, 12 h 00 min";
// How far the wheel brings the view to the house, which a replay frames whole
// with room around it.
const CLOSER_PX = -650;
// Days played, up to the last computed.
const PLAYED_DAYS = 4;

interface KeptRun {
  run_id: string;
  epoch: number;
  scenario_id: string;
  status: string;
  days_computed: number;
  fork: unknown;
}

async function keptRuns(request: APIRequestContext): Promise<KeptRun[]> {
  return await (await request.get("/api/runs")).json();
}

function epochPath({ run_id, epoch }: Pick<KeptRun, "run_id" | "epoch">): string {
  return `/api/runs/${encodeURIComponent(run_id)}/epochs/${epoch}`;
}

function computing(run: KeptRun): boolean {
  return run.status === "queued" || run.status === "running";
}

/** Ends whatever is being computed, which would hold the workers. */
async function stopAll(request: APIRequestContext): Promise<void> {
  for (const run of (await keptRuns(request)).filter(computing)) {
    await request.post(`${epochPath(run)}/stop`);
  }
  await expect
    .poll(async () => (await keptRuns(request)).filter(computing).length, ARRIVES)
    .toBe(0);
}

/** The run to replay, computed by a worker as far as DEMO_DAYS and stopped; or
 * the one a store given again already has, without what recordings left there. */
async function preparedRun(request: APIRequestContext): Promise<KeptRun> {
  await stopAll(request);
  const ofScenario = (await keptRuns(request)).filter((run) => run.scenario_id === SCENARIO);
  const kept = ofScenario.findLast((run) => run.fork === null && run.days_computed >= DAYS);
  for (const run of ofScenario.filter((each) => each !== kept)) {
    await request.post(`${epochPath(run)}/delete`);
  }
  if (kept !== undefined) {
    return kept;
  }
  const started = await request.post(`/api/scenarios/${SCENARIO}/runs`);
  expect(started.ok()).toBe(true);
  const run: KeptRun = await started.json();
  const daysOf = async () => (await (await request.get(epochPath(run))).json()).days_computed;
  await expect.poll(daysOf, { timeout: DAYS * DAY_TAKES_AT_MOST_MS }).toBeGreaterThanOrEqual(DAYS);
  await stopAll(request);
  return run;
}

/** Moves the replay to noon of a day (counted from 1), by the pointer on its
 * timeline, and waits for the scene of that day, the days before it in. */
async function moveToDay(page: Page, day: number): Promise<void> {
  const track = page.getByTestId("replay-track");
  const box = await track.boundingBox();
  if (box === null) {
    throw new Error("the replay's timeline is not on the page");
  }
  await track.click({
    position: { x: (box.width * (day - 0.5)) / RUN_DAYS, y: box.height / 2 },
  });
  await expect(page.getByTestId("replay-moment")).toHaveText(new RegExp(`^Day ${day}, `), ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText(
    `, ${dayCount(day - 1)} in,`,
    ARRIVES,
  );
}

let prepared: KeptRun;

test.beforeAll(async ({ request }) => {
  test.setTimeout(DAYS * DAY_TAKES_AT_MOST_MS * 2);
  prepared = await preparedRun(request);
});

test.afterAll(async ({ request }) => {
  await stopAll(request);
});

test("the README's demo shows the simulator's main features, each under its caption", async ({
  page,
}, testInfo) => {
  // The video started with the page, a moment before the test's body.
  const recording = Date.now();
  test.setTimeout(600_000);

  // The whole house with its crop, the README's preview.
  await page.goto(
    `${VIEWER_PATH}?scenario=${SCENARIO}&field=climate&t=${OPENING_S}&camera=${ON_THE_HOUSE}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText(OPENING_MOMENT, ARRIVES);
  // The house is drawn before its crop, its air after: the shot waits for all.
  await expect(page.getByTestId("scene-status")).toContainText("86 days in,", ARRIVES);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  // Folded away from the view, and kept so from page to page.
  await page.getByRole("button", { name: "Fold the info panel" }).click();
  await page.getByRole("button", { name: "Fold the View panel" }).click();
  await caption(page, "A simulated greenhouse: the house, its climate, each plant organ by organ");
  await markOpening(testInfo, recording);
  await linger(page);

  // The start page: a scenario searched for, its dialog, and a new run.
  await page.goto(LANDING_PATH);
  await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible(
    ARRIVES,
  );
  const search = page.getByRole("combobox", { name: "Scenario" });
  await search.pressSequentially("reference", { delay: 150 });
  const option = page.getByRole("option", { name: /^Reference greenhouse/ });
  await expect(option).toBeVisible(ARRIVES);
  await say(page, "The start page: search for a scenario", 0.6);
  await option.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Reference greenhouse" })).toBeVisible(ARRIVES);
  await say(page, "Its dialog: a new run first, and the runs kept of it under it", 0.6);
  const seed = dialog.getByLabel("Seed", { exact: true });
  await expect(seed).toHaveAttribute("placeholder", "The scenario's own", ARRIVES);
  await expect(seed).toHaveValue("");
  await say(page, "A new run: the seed in grey is the scenario's own, so the same run each time");

  // A run on a worker, followed at its newest day.
  await dialog.getByRole("button", { name: "Start run" }).click();
  await expect(page).toHaveURL(/\/replay\?run=.*&follow=1$/);
  const newRun = replayTarget(new URL(page.url()).search);
  await expect(page.getByTestId("replay-status")).toHaveText("Running", ARRIVES);
  await expect(page.getByRole("button", { name: "Follow the newest day" })).toHaveAttribute(
    "aria-pressed",
    "true",
    ARRIVES,
  );
  await say(page, "A worker computes it, beside the others; its replay follows the newest day");

  // The replay of the run computed before: its timeline, and its days.
  await page.getByRole("link", { name: "Other runs" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: `Replay the run with the scenario's seed, epoch ${prepared.epoch}` })
    .click();
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 00:00", ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText(", 0 days in,", ARRIVES);
  // Once the scene is framed, which the first scene does.
  await page.getByTestId("main-view").hover();
  await page.mouse.wheel(0, CLOSER_PX);
  await say(page, "The replay of a run computed earlier: a timeline under the view, day 1", 0.7);

  const halfway = Math.max(1, Math.round(DAYS / 2));
  await moveToDay(page, halfway);
  await say(page, `Day ${halfway}: anywhere along what is computed, the crop as it stood`, 0.7);

  const late = Math.max(1, DAYS - PLAYED_DAYS);
  await moveToDay(page, late);
  await say(page, `Day ${late}: the crop grown high on its wires`, 0.7);

  await page.getByRole("button", { name: "Open the info panel" }).click();
  await unfold(page, "House air");
  await expect(page.locator("details.house-fold > summary")).not.toContainText("mixing", ARRIVES);
  await say(page, "The panels read the climate at that moment: the air, its humidity, its CO₂");
  await page.getByRole("button", { name: "Fold the info panel" }).click();

  // Played last: a moment asked for after playing waits on what playing asked.
  const transport = page.locator(".replay-transport");
  await transport.getByLabel("Shows a day in").selectOption("2");
  await transport.getByRole("button", { name: "Play" }).click();
  await expect(transport.getByRole("button", { name: "Pause" })).toBeVisible(ARRIVES);
  await say(page, "Played, a day every two seconds: day and night, the crop growing");
  await transport.getByRole("button", { name: "Pause" }).click();
  await expect(transport.getByRole("button", { name: "Play" })).toBeVisible(ARRIVES);

  // A fork, asked first; then a run stopped and resumed.
  await page.getByTestId("replay-fork").click();
  await expect(page.getByTestId("fork-question")).toContainText("beside the others", ARRIVES);
  await say(page, "A fork asks first, and says what it does");
  await page.getByRole("button", { name: "Make the fork" }).click();
  await expect(page.getByTestId("replay-subtitle")).toContainText(/forked from epoch/, ARRIVES);
  await say(page, "The fork, a run of its own from that moment; the run it came from stays", 0.7);

  await page.getByRole("link", { name: "Other runs" }).click();
  const who = `the run with the scenario's seed, epoch ${newRun?.epoch}`;
  const shown = page.getByRole("dialog");
  await shown.getByRole("button", { name: `Stop ${who}` }).click();
  const resume = shown.getByRole("button", { name: `Resume ${who}` });
  await expect(resume).toBeVisible(ARRIVES);
  await say(page, "A run stopped keeps what it computed…", 0.6);
  await resume.click();
  await expect(shown.getByRole("button", { name: `Stop ${who}` })).toBeVisible(ARRIVES);
  await say(page, "…and resumed, it goes on from there, as the same run", 0.6);

  // The builder: a house laid out.
  await page.goto(BUILDER_PATH);
  await page.locator(".builder-form").getByLabel("Identifier").fill("demo_house");
  await page.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-runnable")).toHaveText("It can run.", ARRIVES);
  await expect(page.getByTestId("builder-view").locator("canvas")).toBeVisible(ARRIVES);
  await say(page, "The builder: a house laid out, checked, and drawn as the simulator draws it");
});
