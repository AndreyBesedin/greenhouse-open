import { expect, test } from "@playwright/test";

// A run's checkpoints (P09.5): the climate box, its heater on ten minutes
// into its first day, saved at its second day's start, restored from its
// third, downloaded and uploaded again.
const SCHEDULE = "600:heater:1";
const DAY_S = 86_400;
const ARRIVES = { timeout: 40_000 };

test("checkpoints: a run saved at a day's start is restored, downloaded and uploaded again", async ({
  page,
}) => {
  test.setTimeout(150_000);
  const moment = page.getByTestId("climate-time");
  const panel = page.locator("details.checkpoints");
  const kept = panel.getByTestId("checkpoint");

  await page.goto(`/?scenario=climate_box&field=climate&t=${DAY_S + 3600}&schedule=${SCHEDULE}`);
  await expect(moment).toHaveText("day 1, 1 h 00 min", ARRIVES);
  await panel.locator("summary").click();
  await expect(panel).toContainText("None kept for this scenario.", ARRIVES);

  await test.step("saved at its second day's start", async () => {
    await panel.getByRole("button", { name: "Save day 1's start" }).click();
    await expect(kept).toHaveCount(1, ARRIVES);
    await expect(kept.getByTestId("checkpoint-description")).toHaveText(
      "day 1: 1 commands before it, its scenario's daily commands",
    );
  });

  await test.step("restored from a later day, its run at its moment", async () => {
    await page
      .getByRole("group", { name: "Climate run" })
      .getByRole("button", { name: "Next day" })
      .click();
    await expect(moment).toHaveText("day 2, 1 h 00 min", ARRIVES);
    await kept.getByRole("button", { name: /^Restore day 1, / }).click();
    await expect(page).toHaveURL(new RegExp(`&t=${DAY_S}(&|$)`));
    await expect(page).toHaveURL(/&schedule=600:heater:1(&|$)/);
    await expect(moment).toHaveText("24 h 00 min", ARRIVES);
  });

  await test.step("downloaded as JSON, and uploaded again as the same", async () => {
    const link = kept.getByRole("link", { name: "Download" });
    await expect(link).toHaveAttribute("download", /^climate_box-day-1-[0-9a-f]{16}\.json$/);
    const href = await link.getAttribute("href");
    const document = await (await page.request.get(href ?? "")).body();
    await panel.getByLabel("Upload a checkpoint").setInputFiles({
      name: "checkpoint.json",
      mimeType: "application/json",
      buffer: document,
    });
    await expect(panel.getByTestId("checkpoints-working")).toHaveCount(0, ARRIVES);
    await expect(panel.getByTestId("checkpoints-problem")).toHaveCount(0);
    await expect(kept).toHaveCount(1);
  });

  await test.step("a file that is not one is refused, saying why", async () => {
    await panel.getByLabel("Upload a checkpoint").setInputFiles({
      name: "notes.json",
      mimeType: "application/json",
      buffer: Buffer.from("{"),
    });
    await expect(panel.getByTestId("checkpoints-problem")).toHaveText(
      "the body is not JSON",
      ARRIVES,
    );
  });
});
