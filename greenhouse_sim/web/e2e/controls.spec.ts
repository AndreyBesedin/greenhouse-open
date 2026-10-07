import { expect, type Page, test } from "@playwright/test";

import { simulatedDay } from "./hud";

// live.spec.ts follows climate_box and needs it playing, so these tests take
// another scenario. Every viewer shares a scenario's run, and it outlives a
// test, so each test starts it from a known state.
const SCENARIO = "airflow_box";
const LIVE = `/api/scenarios/${SCENARIO}/live`;
// Eight days' worth at the fastest speed, had the run not been paused.
const HOLD_MS = 1000;

async function openPlaying(page: Page): Promise<void> {
  await page.request.post(`${LIVE}/play`);
  await page.request.post(`${LIVE}/speed?multiplier=1`);
  await page.goto(`/?live=${SCENARIO}`);
  await expect(page.getByTestId("stream-status")).toHaveText("live");
}

test("a live scenario can be paused, stepped, reset and sped up", async ({ page }) => {
  await openPlaying(page);
  const controls = page.getByRole("group", { name: "Time controls" });
  const speed = controls.getByLabel("Speed");
  await expect(speed).toHaveValue("1");

  await speed.selectOption("8");
  await expect(speed).toHaveValue("8");
  await controls.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(controls.getByRole("button", { name: "Play", exact: true })).toBeVisible();

  await controls.getByRole("button", { name: "Reset" }).click();
  await expect.poll(() => simulatedDay(page)).toBe(0);
  await page.waitForTimeout(HOLD_MS);
  expect(await simulatedDay(page)).toBe(0);

  await controls.getByRole("button", { name: "Step" }).click();
  await expect.poll(() => simulatedDay(page)).toBe(1);
  await controls.getByRole("button", { name: "Step" }).click();
  await expect.poll(() => simulatedDay(page)).toBe(2);

  await controls.getByRole("button", { name: "Play", exact: true }).click();
  await expect(controls.getByRole("button", { name: "Step" })).toBeDisabled();
  await expect.poll(() => simulatedDay(page)).toBeGreaterThan(2);
  await expect(page.getByTestId("command-problem")).toHaveCount(0);
});

test("every speed the viewer offers is one the simulator plays at", async ({ page }) => {
  await openPlaying(page);
  const speed = page.getByRole("group", { name: "Time controls" }).getByLabel("Speed");
  const offered = await speed
    .locator("option")
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value));

  for (const value of offered) {
    await speed.selectOption(value);
    await expect(speed).toHaveValue(value);
  }
  await expect(page.getByTestId("command-problem")).toHaveCount(0);
});
