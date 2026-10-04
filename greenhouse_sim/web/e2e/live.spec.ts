import { expect, type Page, test } from "@playwright/test";

const LIVE_STREAM = /\/api\/scenarios\/gh_demo\/live$/;

async function simulatedDay(page: Page): Promise<number> {
  const text = (await page.getByTestId("simulation-time").textContent()) ?? "";
  const match = /^day (\d+) · /.exec(text);
  return match?.[1] === undefined ? -1 : Number(match[1]);
}

test("a live scenario plays one simulated day after another", async ({ page }) => {
  await page.goto("/?live=gh_demo");

  await expect(page.getByTestId("stream-status")).toHaveText("live");
  await expect(page.getByTestId("simulation-time")).toHaveText(
    /^day \d+ · \d{4}-\d{2}-\d{2} 12:00 UTC$/,
  );
  await expect(page.getByTestId("scene-status")).toContainText("scenario gh_demo, live: gh_demo");
  const firstDay = await simulatedDay(page);
  await expect.poll(() => simulatedDay(page)).not.toBe(firstDay);
});

test("a lost stream is reported, and the viewer reconnects by itself", async ({ page }) => {
  await page.route(LIVE_STREAM, (route) => route.abort());

  await page.goto("/?live=gh_demo");
  const stream = page.getByTestId("stream-status");
  await expect(stream).toHaveText("disconnected, reconnecting…");

  await page.unroute(LIVE_STREAM);
  await expect(stream).toHaveText("live", { timeout: 15_000 });
  await expect(page.getByTestId("simulation-time")).toHaveText(/^day \d+ · /);
});
