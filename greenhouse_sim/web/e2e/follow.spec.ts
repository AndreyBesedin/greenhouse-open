import { expect, test } from "@playwright/test";
import { type CameraPose, framing } from "../src/camera.ts";
import { formatPoint } from "../src/readouts.ts";
import { chooser } from "./chooser";

const PLAYBACK = "/api/scenarios/climate_box/playback";
const ARRIVES = { timeout: 60_000 };

test("a view follows its scenario's run as it is played back, the run a consumer reads (P10.2)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // A retry finds the run played back already by the first attempt: the
  // API is the browser tests' own, and keeps it.
  const startedBefore = (await page.request.get(PLAYBACK)).ok();
  await page.goto("/?scenario=climate_box&field=climate&follow=1");
  const panel = page.getByRole("region", { name: "Run played back" });
  const status = panel.getByTestId("playback-status");
  const moment = page.getByTestId("climate-time");

  await test.step("nobody plays it back yet: the view offers to", async () => {
    if (!startedBefore) {
      await expect(status).toHaveText(
        "This scenario's run is not played back yet. Play it back",
        ARRIVES,
      );
      await panel.getByRole("button", { name: "Play it back" }).click();
    }
    await expect(status).toContainText(
      /^Following run climate_box-climate-[0-9a-f]+, epoch 0: /,
      ARRIVES,
    );
  });

  await test.step("it shows the house whole, not its corner, and the address keeps the view", async () => {
    // The climate box's bounds: 12 m by 6.4 m, 4.8 m to its ridge, its
    // footprint's middle at (6, 3.2); the window, 1280 by 720.
    const framed = framing({ x: 6, y: 3.2, z: 0 }, { x: 12, y: 6.4, z: 4.8 }, 1280 / 720);
    // As the address writes a pose: its position, then where it looks.
    const written = [framed.position, framed.target].map(({ x, y, z }) => `${x}:${y}:${z}`);
    await expect(page).toHaveURL((url) => url.searchParams.get("camera") === written.join(","));
    await expect(page.getByTestId("camera-position")).toHaveText(formatPoint(framed.position));
  });

  await test.step("the view's moment follows the run's clock", async () => {
    // A day plays in 10 s: the view moves on with it, a minute at a time.
    const first = await moment.textContent();
    await expect(moment).not.toHaveText(first ?? "", ARRIVES);
  });

  await test.step("its readings name the run the view follows", async () => {
    const shownRun = (await status.textContent())?.match(/Following run (\S+),/)?.[1];
    const played = (await (await page.request.get(PLAYBACK)).json()) as {
      run_id: string;
      time_s: number;
    };
    expect(played.run_id).toBe(shownRun);
    // What the run's sensors delivered by its clock, as the viewer's sensor
    // log asks for it: the same run, by the same name a consumer reads.
    const t = Math.floor(played.time_s / 60) * 60;
    const log = (await (
      await page.request.get(`/api/scenarios/climate_box/climate/observations?t=${t}`)
    ).json()) as { run_id: string; observations: { source: { source_id: string } }[] };
    expect(log.run_id).toBe(shownRun);
    expect(new Set(log.observations.map((o) => o.source.source_id))).toEqual(new Set([shownRun]));
  });

  await test.step("paused, it holds; a change of the run is said to be another run", async () => {
    await panel.getByRole("button", { name: "Pause" }).click();
    await expect(status).toContainText("paused");
    await page.goto("/?scenario=climate_box&field=climate&follow=1&set=heater:1");
    await expect(panel.getByTestId("playback-another-run")).toContainText(
      "it changes its equipment",
      ARRIVES,
    );
    await panel.getByRole("button", { name: "Draw the run played back" }).click();
    await expect(panel.getByTestId("playback-another-run")).toHaveCount(0);
    await expect(page).not.toHaveURL(/set=heater/);
  });
});

test("a moment whose field fails does not stop the view following the run's clock", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // Played back, started here if no test has yet, and playing.
  expect((await page.request.post(`${PLAYBACK}/start`)).ok()).toBe(true);
  // Every field asked for after the first fails.
  let asked = 0;
  await page.route("**/api/scenarios/climate_box/fields/climate*", (route) => {
    asked += 1;
    return asked === 1
      ? route.continue()
      : route.fulfill({ status: 500, json: { error: "a failure for the test" } });
  });
  await page.goto("/?scenario=climate_box&field=climate&follow=1");
  // The moment asked for, as the address keeps it; the one drawn stays the
  // last whose field arrived.
  const asking = () => Number(new URL(page.url()).searchParams.get("t") ?? 0);

  // Moved on once, to the clock, whose field fails; then on again, with it,
  // and again.
  let now = asking();
  for (let step = 0; step < 3; step += 1) {
    await expect.poll(asking, ARRIVES).toBeGreaterThan(now);
    now = asking();
  }
  await expect(page.getByTestId("climate-failed")).toContainText("cannot be drawn");
  expect(asked).toBeGreaterThan(2);
});

test("followed, the house is framed as the latest scene has it, again as the window narrows, never once moved", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // The climate box's own bounds, as the API draws them.
  const base = { x: 6, y: 3.2, z: 0 };
  const size = { x: 12, y: 6.4, z: 4.8 };
  const written = ({ position, target }: CameraPose) =>
    [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
  const camera = () => new URL(page.url()).searchParams.get("camera");

  await test.step("followed from a longer house on show, its own is framed", async () => {
    // The longer house stays on show until the scenario's own arrives: the
    // framing waits for that.
    await page.goto("/?scenario=climate_box&envelope=length:20");
    await expect(page.getByTestId("scene-status")).toContainText("entities", ARRIVES);
    await (await chooser(page)).getByRole("button", { name: "Follow climate_box" }).click();
    await expect.poll(camera, ARRIVES).toBe(written(framing(base, size, 1280 / 720)));
  });

  await test.step("the window made narrow, as beside a consumer's, it is framed again", async () => {
    await page.setViewportSize({ width: 540, height: 720 });
    await expect.poll(camera, ARRIVES).toBe(written(framing(base, size, 540 / 720)));
  });

  await test.step("moved by a person, it stays where they put it as the window widens", async () => {
    const view = await page.getByTestId("main-view").locator("canvas").boundingBox();
    if (view === null) {
      throw new Error("the 3D view is not on the page");
    }
    const at = { x: view.x + view.width / 2, y: view.y + 80 };
    await page.mouse.move(at.x, at.y);
    await page.mouse.down();
    await page.mouse.move(at.x + 120, at.y + 20, { steps: 8 });
    await page.mouse.up();
    const narrow = written(framing(base, size, 540 / 720));
    await expect(page.getByTestId("camera-position")).not.toHaveText(
      formatPoint(framing(base, size, 540 / 720).position),
    );
    await page.setViewportSize({ width: 1280, height: 720 });
    // Long enough for the view to have sampled its camera, and answered.
    await page.waitForTimeout(2000);
    expect(camera()).toBe(narrow);
  });
});
