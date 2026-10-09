import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * P05's final QA, `climate-actuators`, at runtime in the climate box:
 * toggle the fan, vary the heater's power, toggle the dehumidifier, open and
 * close the roof vent, watch the arrows and the temperature and humidity
 * slices, and read fixed probes and their charts. The fan must change the
 * air's direction and speed near it, the heater warm the air, the
 * dehumidifier dry it, the vent change the air at its boundary, and the
 * same schedule must replay to the same run exactly.
 */

// In the fan's core, beside the heater, beside the dehumidifier, and under
// the roof vent.
const PROBES = "3:3.2:2.8,10.5:1:0.75,6:5.3:0.75,6:2.5:3.75";
// A moment of a run can take CI's simulator a while, behind the scene and
// the charts it is asked for beside it.
const ARRIVES_MS = 20_000;

/** A number a probe's reading gives, after its name. */
async function reads(reading: Locator, name: "temperature" | "humidity"): Promise<number> {
  const text = (await reading.textContent()) ?? "";
  const found = new RegExp(`${name} (-?[\\d.]+)`).exec(text);
  if (found?.[1] === undefined) {
    throw new Error(`no ${name} in "${text}"`);
  }
  return Number(found[1]);
}

async function speedOf(reading: Locator): Promise<number> {
  const found = /^climate: ([\d.]+) m\/s/.exec((await reading.textContent()) ?? "");
  return Number(found?.[1]);
}

async function moveTo(page: Page, seconds: number): Promise<void> {
  await page.getByRole("slider", { name: "Time into the run" }).fill(String(seconds));
  await expect(page).toHaveURL(seconds === 0 ? /^(?!.*&t=)/ : new RegExp(`&t=${seconds}(&|$)`));
  // Shown once that moment's field has arrived.
  await expect(page.getByTestId("climate-time")).toHaveText(`${seconds / 60} min`, {
    timeout: ARRIVES_MS,
  });
}

test("climate-actuators: the box's equipment and vent change its air, visibly and measurably", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto(`/?scenario=climate_box&field=climate&probes=${PROBES}`);
  const equipment = page.getByRole("group", { name: "Equipment" });
  const status = page.getByTestId("field-status");
  const core = page.getByTestId("probe-1-reading");
  const byHeater = page.getByTestId("probe-2-reading");
  const byDehumidifier = page.getByTestId("probe-3-reading");
  const underVent = page.getByTestId("probe-4-reading");
  await expect(status).toContainText("air speed 0 to 0 m/s.");

  await test.step("the fan changes the air's direction and speed near it", async () => {
    await equipment.getByRole("checkbox", { name: "fan" }).check();
    await expect(status).toContainText("air speed 0 to 4.81 m/s.");
    await expect(core).toHaveText(/^climate: 4\.34 m\/s \(4\.34, 0\.00, 0\.01\)/);
    await equipment.getByRole("checkbox", { name: "fan" }).uncheck();
    await expect(core).toHaveText(/^climate: 0\.00 m\/s/);
  });

  await test.step("the heater warms the air, the more the higher its power", async () => {
    await moveTo(page, 600);
    const unheated = await reads(byHeater, "temperature");
    await moveTo(page, 0);
    await equipment.getByRole("checkbox", { name: "heater" }).check();
    await moveTo(page, 600);
    await expect(byHeater).toHaveText(/temperature 37\.03 °C/);
    await moveTo(page, 0);
    await equipment.getByRole("slider", { name: "heater level" }).fill("50");
    await expect(page.getByTestId("equipment-heater")).toHaveText("50%, 5 kW");
    await moveTo(page, 600);
    const half = await reads(byHeater, "temperature");
    expect(unheated).toBeLessThan(11);
    expect(half).toBeGreaterThan(unheated + 5);
    expect(half).toBeLessThan(37.03);
  });

  await test.step("the dehumidifier dries the air around it", async () => {
    const before = await reads(byDehumidifier, "humidity");
    await moveTo(page, 0);
    await equipment.getByRole("checkbox", { name: "dehumidifier" }).check();
    await moveTo(page, 600);
    await expect.poll(async () => reads(byDehumidifier, "humidity")).toBeLessThan(before - 5);
  });

  await test.step("the roof vent changes the air at its boundary, and closed, leaves it", async () => {
    const shut = (await underVent.textContent()) ?? "";
    const vent = page.getByRole("group", { name: "Openings" }).getByRole("slider").first();
    await vent.fill("100");
    await expect(page.getByTestId("opening-roof_vent")).toHaveText("100%, 3.77 m²");
    await expect.poll(async () => speedOf(underVent)).toBeGreaterThan(0.2);
    expect(await reads(underVent, "temperature")).toBeLessThan(
      Number(/temperature ([\d.]+)/.exec(shut)?.[1]),
    );
    await vent.fill("0");
    await expect(underVent).toHaveText(shut);
  });

  await test.step("the arrows, and the temperature and humidity slices, show it", async () => {
    await expect(page.getByRole("radio", { name: "arrows" })).toBeChecked();
    await page.getByRole("radio", { name: "slice" }).check();
    await page.getByRole("combobox", { name: "Slice of" }).selectOption("temperature");
    await expect(page.getByTestId("field-legend-quantity")).toHaveText("temperature (°C)");
    await page.getByRole("combobox", { name: "Slice of" }).selectOption("humidity");
    await expect(page.getByTestId("field-legend-quantity")).toHaveText("humidity (%)");
  });

  await test.step("fixed probes are charted through the run, beside it all off", async () => {
    const charts = page.getByRole("region", { name: "Probe charts" });
    await expect(charts.locator("polyline")).toHaveCount(4 * 3 * 2);
    const charted = page.getByTestId("chart-P2-temperature_c");
    const shown = await reads(byHeater, "temperature");
    await expect(charted).toHaveText(new RegExp(`^temperature ${shown.toFixed(2)} °C, all off`));
  });

  await test.step("the same schedule replays to the same run exactly", async () => {
    const address = page.url();
    const readings = await Promise.all(
      [core, byHeater, byDehumidifier, underVent].map((reading) => reading.textContent()),
    );
    await page.goto(address);
    for (const [index, reading] of [core, byHeater, byDehumidifier, underVent].entries()) {
      await expect(reading).toHaveText(readings[index] ?? "");
    }
  });
});
