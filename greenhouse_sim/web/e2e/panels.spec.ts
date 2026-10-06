import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

for (const size of [
  { width: 1280, height: 720 },
  { width: 1000, height: 480 },
  { width: 640, height: 480 },
  { width: 360, height: 640 },
]) {
  test(`panels stay apart and controls remain reachable at ${size.width} by ${size.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await page.goto("/?scene=example");
    await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene");
    await page.getByLabel("Colour by").selectOption("visible_height_cm");
    await page.getByRole("button", { name: "Isometric", exact: true }).click();
    // The upper part of the canvas stays available even above the narrow dock.
    await selectAt(page, { x: 0.5, y: 1.6, z: 0.15 }, "gh_demo_plant_001");

    const panels = page.locator(".viewer-panels");
    const boxes = await panels.locator(":scope > *").evaluateAll((elements) =>
      elements.map((element) => {
        const { x, y, width, height } = element.getBoundingClientRect();
        return { x, y, width, height };
      }),
    );
    for (const [index, box] of boxes.entries()) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(size.width);
      for (const other of boxes.slice(index + 1)) {
        const overlapX =
          Math.min(box.x + box.width, other.x + other.width) - Math.max(box.x, other.x);
        const overlapY =
          Math.min(box.y + box.height, other.y + other.height) - Math.max(box.y, other.y);
        expect(overlapX <= 0 || overlapY <= 0, "panels must not overlap").toBe(true);
      }
    }

    const overlays = page.getByRole("group", { name: "Overlays" });
    await overlays.getByLabel("Label", { exact: true }).uncheck();
    await expect(page.getByTestId("debug-label")).toHaveCount(0);
    await overlays.getByLabel("Label", { exact: true }).check();
    await expect(page.getByTestId("debug-label")).toHaveCount(1);
    await page.getByRole("figure", { name: "Legend", exact: true }).scrollIntoViewIfNeeded();
    await expect(page.getByTestId("legend-property")).toBeInViewport();
    await page.getByRole("button", { name: "Clear selection", exact: true }).click();
    await expect(page.getByRole("region", { name: "Inspector" })).toHaveCount(0);

    if (size.width <= 840) {
      const dock = await panels.boundingBox();
      expect(dock).not.toBeNull();
      expect(dock?.height).toBeLessThanOrEqual(size.height * 0.45);
      // Scroll back to the source picker and exercise it, rather than just
      // checking the canvas dimensions while its controls are obscured.
      await page.getByRole("button", { name: "Reference scene", exact: true }).click();
      await expect(page.getByTestId("scene-status")).toContainText("reference scene");
    }
  });
}
