import { expect, test } from "@playwright/test";

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
