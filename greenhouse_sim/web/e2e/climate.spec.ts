import { expect, test } from "@playwright/test";

// Three probes on the climate box's fan's axis, 2.8 m up along the middle of
// the house, from its rotor at x = 1 m: in its 3 m core, far down the house,
// and behind it, where it draws its air from.
const ON_ITS_AXIS = "3:3.2:2.8,9:3.2:2.8,0.5:3.2:2.8";

test("climate: a running fan drives the air along its axis, and its level sets how hard", async ({
  page,
}) => {
  await page.goto(`/?scenario=climate_box&field=climate&probes=${ON_ITS_AXIS}`);
  const status = page.getByTestId("field-status");
  const equipment = page.getByRole("group", { name: "Equipment" });
  const inTheCore = page.getByTestId("probe-1-reading");
  const farDown = page.getByTestId("probe-2-reading");
  const behind = page.getByTestId("probe-3-reading");

  await test.step("with the fan off, the box's air is still, at its starting 16 °C", async () => {
    await expect(status).toHaveText(
      "climate_box_climate (climate:prescribed:uniform): 24 × 13 × 8 cells, air speed 0 to 0 m/s.",
    );
    await expect(inTheCore).toHaveText(
      "climate: 0.00 m/s (0.00, 0.00, 0.00), temperature 16.00 °C",
    );
  });

  await test.step("switched on, it blows down the house, slowing as its jet spreads", async () => {
    await equipment.getByRole("checkbox", { name: "fan" }).check();
    await expect(page).toHaveURL(/&set=fan:1(&|$)/);
    await expect(status).toContainText("air speed 0 to 4.81 m/s.");
    await expect(inTheCore).toHaveText(/^climate: 4\.34 m\/s \(4\.34, 0\.00, 0\.01\)/);
    await expect(farDown).toHaveText(/^climate: 1\.70 m\/s \(1\.70, -?0\.00, -?0\.00\)/);
    // Drawn in from behind it.
    await expect(behind).toHaveText(/^climate: 0\.75 m\/s \(0\.75, 0\.00, 0\.01\)/);
  });

  await test.step("at half its level, the air moves half as fast", async () => {
    await equipment.getByRole("slider", { name: "fan level" }).fill("50");
    await expect(page).toHaveURL(/&set=fan:0\.5(&|$)/);
    await expect(inTheCore).toHaveText(/^climate: 2\.17 m\/s/);
    await expect(farDown).toHaveText(/^climate: 0\.85 m\/s/);
  });

  await test.step("switched off, the air is still again", async () => {
    await equipment.getByRole("checkbox", { name: "fan" }).uncheck();
    await expect(status).toContainText("air speed 0 to 0 m/s.");
  });
});

// Beside the climate box's heater, in its back right corner, and in the
// middle of the house, both 0.75 m up, on a slice of its temperature there.
const BY_THE_HEATER = "10.5:1:0.75,6:3.2:0.75";

test("climate: a running heater warms its corner and the house through the run", async ({
  page,
}) => {
  await page.goto(
    `/?scenario=climate_box&set=heater:1&field=climate&fieldView=slice&slice=temperature:z:0.75&probes=${BY_THE_HEATER}`,
  );
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const corner = page.getByTestId("probe-1-reading");
  const middle = page.getByTestId("probe-2-reading");

  await test.step("at the run's start, the air is 16 °C everywhere", async () => {
    await expect(moment).toHaveText("0 min");
    await expect(corner).toHaveText(/temperature 16\.00 °C$/);
    await expect(middle).toHaveText(/temperature 16\.00 °C$/);
  });

  await test.step("ten minutes in, its corner is warm, and the cold glass cools the rest", async () => {
    await run.getByRole("slider", { name: "Time into the run" }).fill("600");
    await expect(page).toHaveURL(/&t=600(&|$)/);
    await expect(moment).toHaveText("10 min");
    await expect(corner).toHaveText(/temperature 31\.88 °C$/);
    await expect(middle).toHaveText(/temperature 14\.96 °C$/);
  });

  await test.step("played, the run moves on a minute at a time, until paused", async () => {
    await run.getByRole("button", { name: "Play" }).click();
    await expect(moment).toHaveText("11 min");
    await expect(moment).toHaveText("12 min");
    await run.getByRole("button", { name: "Pause" }).click();
    await expect(run.getByRole("button", { name: "Play" })).toBeVisible();
  });

  await test.step("without the heater, the house has cooled towards the 8 °C outside", async () => {
    await page.getByRole("slider", { name: "Time into the run" }).fill("600");
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .uncheck();
    await expect(middle).toHaveText(/temperature 9\.13 °C$/);
  });
});
