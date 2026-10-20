import { expect, type Page, type Route, test } from "@playwright/test";

// The climate box's runs last its 14 days (P09.2): its heater on ten minutes
// into the first, and off an hour into the second.
const SCHEDULE = "600:heater:1,90000:heater:0";
const DAY_S = 86_400;
// A moment on a later day takes the simulator a grid run of its own; the
// heater's level is the scene's, asked for beside it.
const ARRIVES = { timeout: 40_000 };

/** Whether a request asks for the climate's field at `time`. */
function fieldAt(time: number): (url: URL) => boolean {
  return (url) =>
    url.pathname.endsWith("/fields/climate") && url.searchParams.get("t") === String(time);
}

/** Holds the request for the climate's field at `time` until the test
 * lets it through, or for good; `held` is that request, once it is made.
 * (Wrapped, since an async function's promise of a promise would wait for
 * the request itself.) */
async function holdField(page: Page, time: number): Promise<{ held: Promise<Route> }> {
  let receive: (route: Route) => void = () => undefined;
  const held = new Promise<Route>((resolve) => {
    receive = resolve;
  });
  await page.route(fieldAt(time), (route) => receive(route));
  return { held };
}

test("season: the time controls span the run's days, each chart its moment's day", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto(`/?scenario=climate_box&field=climate&t=600&schedule=${SCHEDULE}`);
  const run = page.getByRole("group", { name: "Climate run" });
  const day = run.getByRole("slider", { name: "Day of the run" });
  const moment = page.getByTestId("climate-time");
  const heater = page.getByTestId("equipment-heater");
  const markers = page.getByRole("region", { name: "Schedule" }).getByTestId("schedule-marker");

  await test.step("on the first day, there is no day before it", async () => {
    await expect(moment).toHaveText("10 min", ARRIVES);
    await expect(day).toHaveValue("0");
    await expect(run.getByRole("button", { name: "Previous day" })).toBeDisabled();
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
    // The bar is the day's: only the first command lies on it.
    await expect(markers).toHaveCount(1);
  });

  await test.step("a day on, the same time of day, and the weather of that day", async () => {
    const weatherDay = page.waitForRequest(/\/weather\/day\?t=172800/);
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(page).toHaveURL(new RegExp(`&t=${DAY_S + 600}(&|$)`));
    await expect(moment).toHaveText("day 1, 10 min", ARRIVES);
    await weatherDay;
    await expect(day).toHaveValue("1");
    // Still on from the first day, until its command an hour in.
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
    await expect(markers).toHaveCount(1);
    await expect(page.getByTestId("house-air")).toBeVisible();
    await run.getByRole("slider", { name: "Time of day" }).fill("3600");
    await expect(moment).toHaveText("day 1, 1 h 00 min", ARRIVES);
    await expect(heater).toHaveText("off", ARRIVES);
  });

  await test.step("on its last day, there is none after it", async () => {
    await day.fill("13");
    await expect(moment).toHaveText("day 13, 1 h 00 min", ARRIVES);
    await expect(run.getByRole("button", { name: "Next day" })).toBeDisabled();
    await expect(markers).toHaveCount(0);
  });

  await test.step("played a day a step, it keeps its time of day, and stops at the end", async () => {
    await day.fill("12");
    await expect(moment).toHaveText("day 12, 1 h 00 min", ARRIVES);
    await run.getByRole("combobox", { name: "Pace" }).selectOption({ label: "1 day a step" });
    await run.getByRole("button", { name: "Play" }).click();
    await expect(moment).toHaveText("day 13, 1 h 00 min", ARRIVES);
    await expect(moment).toHaveText("day 13, 24 h 00 min", ARRIVES);
    await expect(run.getByRole("button", { name: "Play" })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`&t=${14 * DAY_S}(&|$)`));
  });
});

test("season: a day on its way says so, play waits for it, and one that cannot be drawn stops play", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await page.goto(`/?scenario=climate_box&field=climate&t=600&schedule=${SCHEDULE}`);
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const pending = page.getByTestId("climate-pending");
  await expect(moment).toHaveText("10 min", ARRIVES);
  await expect(pending).toBeHidden(ARRIVES);

  await test.step("a step on says which day it is loading, and a step past it gives it up", async () => {
    // Else every day stepped past is asked for to the end, each holding
    // one of the browser's few connections to the API (#202).
    await holdField(page, DAY_S + 600);
    const givenUp = page.waitForEvent("requestfailed", (request) =>
      fieldAt(DAY_S + 600)(new URL(request.url())),
    );
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(pending).toHaveText(/^Loading day 1, 10 min… \d+ s$/);
    await expect(moment).toHaveText("10 min");

    await run.getByRole("button", { name: "Next day" }).click();
    await givenUp;
    await expect(moment).toHaveText("day 2, 10 min", ARRIVES);
    await expect(pending).toBeHidden();
  });

  await test.step("play waits for the day it asked for, says so, and pauses and resumes there", async () => {
    const { held } = await holdField(page, 3 * DAY_S + 600);
    await run.getByRole("combobox", { name: "Pace" }).selectOption({ label: "1 day a step" });
    await run.getByRole("button", { name: "Play" }).click();
    const route = await held;
    await expect(pending).toHaveText(/^Playing: waiting for day 3, 10 min… \d+ s$/);

    await run.getByRole("button", { name: "Pause" }).click();
    await expect(pending).toHaveText(/^Loading day 3, 10 min… \d+ s$/);
    await run.getByRole("button", { name: "Play" }).click();
    await expect(pending).toHaveText(/^Playing: waiting for day 3, 10 min… \d+ s$/);
    // The next day's field fails, once play moves on to it.
    await page.route(fieldAt(4 * DAY_S + 600), (failing) =>
      failing.fulfill({ status: 500, json: { error: "a failure for the test" } }),
    );
    await route.continue();
    await expect(moment).toHaveText("day 3, 10 min", ARRIVES);
  });

  await test.step("a day that cannot be drawn stops play, which says what is drawn instead", async () => {
    await expect(page.getByTestId("climate-failed")).toHaveText(
      "Day 4, 10 min cannot be drawn; day 3, 10 min is shown.",
      ARRIVES,
    );
    await expect(run.getByRole("button", { name: "Play" })).toBeVisible();
    await expect(moment).toHaveText("day 3, 10 min");
    await expect(page.getByTestId("scene-failures")).toHaveText(
      "Not drawn as asked: the field is not available (the simulator API answered 500).",
    );
    // The field drawn is day 3's still, not taken off the view.
    await expect(page.getByTestId("field-status")).toContainText("cells");
  });
});

test("season: play and pause pressed in a hurry while a day is on its way end as last pressed, and resume from there (#202)", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await page.goto(`/?scenario=climate_box&field=climate&t=600&schedule=${SCHEDULE}`);
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const pending = page.getByTestId("climate-pending");
  const toggle = run.getByRole("button", { name: /^(Play|Pause)$/ });
  await expect(moment).toHaveText("10 min", ARRIVES);
  await expect(pending).toBeHidden(ARRIVES);

  await test.step("pressed seven times while day 1 is held, it ends paused, waiting for nothing new", async () => {
    const { held } = await holdField(page, DAY_S + 600);
    await run.getByRole("combobox", { name: "Pace" }).selectOption({ label: "1 day a step" });
    await toggle.click();
    const route = await held;
    for (let pressed = 0; pressed < 7; pressed++) {
      await toggle.click();
    }
    await expect(toggle).toHaveText("Play");
    await expect(pending).toHaveText(/^Loading day 1, 10 min… \d+ s$/);
    // No step after day 1 is asked for while paused, before or after it
    // arrives.
    const later: string[] = [];
    page.on("request", (request) => {
      const t = Number(new URL(request.url()).searchParams.get("t"));
      if (request.url().includes("/fields/climate") && t > DAY_S + 600) {
        later.push(request.url());
      }
    });
    await route.continue();
    await expect(moment).toHaveText("day 1, 10 min", ARRIVES);
    await expect(pending).toBeHidden();
    await page.waitForTimeout(2000);
    await expect(moment).toHaveText("day 1, 10 min");
    expect(later).toEqual([]);
  });

  await test.step("played again, it moves on from the day it stopped at", async () => {
    await toggle.click();
    await expect(moment).toHaveText("day 2, 10 min", ARRIVES);
    await toggle.click();
    await expect(toggle).toHaveText("Play");
  });
});
