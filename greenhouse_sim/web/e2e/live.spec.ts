import { expect, test } from "@playwright/test";

import { simulatedDay } from "./hud";

const LIVE_STREAM = /\/api\/scenarios\/climate_box\/live$/;

test("a live scenario plays one simulated day after another", async ({ page }) => {
  await page.goto("/?live=climate_box");

  await expect(page.getByTestId("stream-status")).toHaveText("live");
  await expect(page.getByTestId("simulation-time")).toHaveText(
    /^day \d+ · \d{4}-\d{2}-\d{2} 12:00 UTC$/,
  );
  await expect(page.getByTestId("scene-status")).toContainText(
    "scenario climate_box, live: climate_box",
  );
  const firstDay = await simulatedDay(page);
  await expect.poll(() => simulatedDay(page)).not.toBe(firstDay);
});

test("a lost stream is reported, and the viewer reconnects by itself", async ({ page }) => {
  await page.route(LIVE_STREAM, (route) => route.abort());

  await page.goto("/?live=climate_box");
  const stream = page.getByTestId("stream-status");
  await expect(stream).toHaveText("disconnected, reconnecting…");

  await page.unroute(LIVE_STREAM);
  await expect(stream).toHaveText("live", { timeout: 15_000 });
  await expect(page.getByTestId("simulation-time")).toHaveText(/^day \d+ · /);
});
