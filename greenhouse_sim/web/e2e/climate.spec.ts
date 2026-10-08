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
      "climate: 0.00 m/s (0.00, 0.00, 0.00), temperature 16.00 °C, humidity 85.00 %",
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
    await expect(corner).toHaveText(/temperature 16\.00 °C, humidity 85\.00 %$/);
    await expect(middle).toHaveText(/temperature 16\.00 °C, humidity 85\.00 %$/);
  });

  await test.step("ten minutes in, its corner is warm, and the cold glass cools the rest", async () => {
    await run.getByRole("slider", { name: "Time into the run" }).fill("600");
    await expect(page).toHaveURL(/&t=600(&|$)/);
    await expect(moment).toHaveText("10 min");
    // Warmed, the corner's air is far from saturated.
    await expect(corner).toHaveText(/temperature 31\.88 °C, humidity 31\.58 %$/);
    await expect(middle).toHaveText(/temperature 14\.96 °C, humidity 84\.80 %$/);
  });

  await test.step("played, the run moves on a minute at a time, until paused", async () => {
    await run.getByRole("button", { name: "Play" }).click();
    await expect(moment).toHaveText("11 min");
    await expect(moment).toHaveText("12 min");
    await run.getByRole("button", { name: "Pause" }).click();
    await expect(run.getByRole("button", { name: "Play" })).toBeVisible();
  });

  await test.step("switched off ten minutes in, the house cools to 9 °C and saturates", async () => {
    const slider = page.getByRole("slider", { name: "Time into the run" });
    await slider.fill("600");
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .uncheck();
    // An override at its moment: the air then is as it was.
    await expect(page).toHaveURL(/&schedule=600:heater:0(&|$)/);
    await expect(middle).toHaveText(/temperature 14\.96 °C, humidity 84\.80 %$/);
    await slider.fill("1200");
    await expect(middle).toHaveText(/temperature 9\.06 °C, humidity 100\.00 %$/);
  });
});

// Beside the climate box's dehumidifier, halfway along its left wall, and in
// its front right corner, both 0.75 m up, on a slice of the relative humidity.
const BY_THE_DEHUMIDIFIER = "6:5.3:0.75,2:1:0.75";

test("climate: a running dehumidifier dries the air around it", async ({ page }) => {
  await page.goto(
    `/?scenario=climate_box&set=dehumidifier:1&field=climate&fieldView=slice&slice=humidity:z:0.75&t=600&probes=${BY_THE_DEHUMIDIFIER}`,
  );
  const beside = page.getByTestId("probe-1-reading");
  const far = page.getByTestId("probe-2-reading");
  await expect(page.getByTestId("field-legend-quantity")).toHaveText("humidity (%)");

  await test.step("ten minutes in, it has dried and warmed its side of the cooling house", async () => {
    await expect(beside).toHaveText(/temperature 11\.26 °C, humidity 87\.38 %$/);
    // Unheated, the far corner has cooled to saturation.
    await expect(far).toHaveText(/temperature 9\.70 °C, humidity 99\.93 %$/);
  });

  await test.step("with the heater on too from the start, the whole house is drier", async () => {
    const slider = page.getByRole("slider", { name: "Time into the run" });
    // Set at the start, not overridden ten minutes in.
    await slider.fill("0");
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .check();
    await expect(page).toHaveURL(/set=dehumidifier:1,heater:1(&|$)/);
    await slider.fill("600");
    await expect(beside).toHaveText(/temperature 16\.59 °C, humidity 73\.19 %$/);
    await expect(far).toHaveText(/temperature 12\.87 °C, humidity 95\.72 %$/);
  });
});

// Under the climate box's roof vent, in the top layer of its air.
const UNDER_THE_ROOF_VENT = "6:2.5:3.75";

test("climate: opening the roof vent lets the heated air out, and the cold in", async ({
  page,
}) => {
  await page.goto(
    `/?scenario=climate_box&set=heater:1&field=climate&t=600&probes=${UNDER_THE_ROOF_VENT}`,
  );
  const reading = page.getByTestId("probe-1-reading");

  await test.step("shut, the air under it is still, and warm from the heater", async () => {
    await expect(reading).toHaveText(
      "climate: 0.00 m/s (0.00, 0.00, 0.00), temperature 14.42 °C, humidity 87.77 %",
    );
  });

  await test.step("open, the warmer air goes out through it, and the house cools", async () => {
    await page.getByRole("group", { name: "Openings" }).getByRole("slider").first().fill("100");
    await expect(page).toHaveURL(/open=roof_vent:1(&|$)/);
    await expect(reading).toHaveText(
      "climate: 0.29 m/s (0.00, 0.00, 0.29), temperature 9.66 °C, humidity 86.87 %",
    );
  });
});
