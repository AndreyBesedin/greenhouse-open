import { expect, test } from "@playwright/test";
import { chooser } from "./chooser";

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
    // The upper part of the canvas stays available even above the narrow dock:
    // the example's front path, near the corner the camera looks at.
    await selectAt(page, { x: 0.9, y: 1.6, z: 0 }, "climate_box_front_path");

    const panels = page.locator(".viewer-panels");
    const boxes = await panels
      .locator(".info-panel, .hud, .inspector, .legends")
      .evaluateAll((elements) =>
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
      await (await chooser(page)).getByRole("button", { name: "Empty grid", exact: true }).click();
      await expect(page.getByTestId("scene-status")).toContainText("empty grid");
    }
  });
}

test("at the usual window size, the info panel shows all of itself beside a tall legend", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/?scenario=tomato_compartment");
  await expect(page.getByTestId("scene-status")).toContainText(
    "Showing the scenario tomato_compartment",
  );
  // The tallest legend there is, on the other side of the view.
  // "Surface categories", or "Categories" once the layout has some too.
  await page.getByRole("checkbox", { name: /categories$/i }).check();
  await expect(page.getByTestId("category")).toHaveCount(7);

  const infoPanel = page.locator(".info-panel");
  const { scrollHeight, clientHeight } = await infoPanel.evaluate((element) => ({
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  }));
  expect(scrollHeight).toBeLessThanOrEqual(clientHeight);
  // Opened, the choice of what to show is at its top, every scenario in sight.
  await expect(
    (await chooser(page)).getByRole("button", { name: "Open climate_box" }),
  ).toBeInViewport({ ratio: 1 });
  // The HUD keeps its width, so that its readings stay on one line each.
  expect((await page.locator(".hud").boundingBox())?.width).toBe(324);
});

test("the HUD folds to its header, and moves by it, never out of the window (#204)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene");
  const hud = page.getByRole("region", { name: "View" });
  const header = hud.locator("summary");
  const top = hud.getByRole("button", { name: "Top", exact: true });
  const putBack = hud.getByRole("button", { name: "Put it back" });
  const box = async () => {
    const found = await hud.boundingBox();
    if (found === null) {
      throw new Error("the HUD is not drawn");
    }
    return found;
  };
  // Where it stands, and how wide: its height follows its readouts.
  const place = async () => {
    const { x, y, width } = await box();
    return { x, y, width };
  };
  /** Drags the HUD's header by (dx, dy), in steps, as a person would. */
  const dragBy = async (dx: number, dy: number) => {
    const grip = await header.boundingBox();
    if (grip === null) {
      throw new Error("the HUD's header is not drawn");
    }
    const from = { x: grip.x + grip.width / 2, y: grip.y + grip.height / 2 };
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(from.x + dx, from.y + dy, { steps: 8 });
    await page.mouse.up();
  };
  await expect(hud.getByTestId("object-count")).not.toHaveText("…");
  const inPlace = await place();

  await test.step("a click on its header folds it to a tab, and another unfolds it", async () => {
    // It folds and unfolds on the details' toggle, a moment after the click.
    await header.click();
    await expect(top).toBeHidden();
    await expect.poll(async () => (await place()).width).toBeLessThan(inPlace.width / 2);
    await header.click();
    await expect(top).toBeVisible();
    await expect.poll(place).toEqual(inPlace);
  });

  await test.step("dragged by its header, it moves with the pointer and stays unfolded", async () => {
    await dragBy(-400, 150);
    const moved = await box();
    expect(moved.x).toBeCloseTo(inPlace.x - 400, 0);
    expect(moved.y).toBeCloseTo(inPlace.y + 150, 0);
    await expect(top).toBeVisible();
    // The camera's presets still work from where it is.
    await top.click();
  });

  await test.step("dragged past the window's corner, it stops at its edges", async () => {
    await dragBy(-3000, 3000);
    const cornered = await box();
    expect(cornered.x).toBeCloseTo(0, 0);
    expect(cornered.y + cornered.height).toBeCloseTo(720, 0);
  });

  await test.step("a smaller window brings it back within", async () => {
    await page.setViewportSize({ width: 1280, height: 600 });
    await expect
      .poll(async () => {
        const { y, height } = await box();
        return y + height;
      })
      .toBeLessThanOrEqual(600);
  });

  await test.step("put back, it is where it was", async () => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await putBack.click();
    await expect(putBack).toBeHidden();
    expect(await place()).toEqual(inPlace);
  });
});

test("the panels are dark, or light if chosen, and the golden views keep theirs light (#208)", async ({
  page,
}) => {
  const background = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((element) => getComputedStyle(element).backgroundColor);
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene");

  // Dark navy by default, its text light.
  expect(await background(".info-panel")).toBe("rgba(17, 24, 39, 0.9)");
  expect(await background(".hud")).toBe("rgba(17, 24, 39, 0.9)");

  // Light, once chosen, and still so after a reload.
  await page.getByRole("checkbox", { name: "Light panels" }).check();
  expect(await background(".info-panel")).toBe("rgba(255, 255, 255, 0.88)");
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Light panels" })).toBeChecked();
  expect(await background(".info-panel")).toBe("rgba(255, 255, 255, 0.88)");
  await page.getByRole("checkbox", { name: "Light panels" }).uncheck();

  // A golden view's caption is light whatever the viewer's panels are.
  await page.goto("/qa/renderer?seed=42");
  expect(await background(".qa-caption")).toBe("rgba(255, 255, 255, 0.88)");
});
