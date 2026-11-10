import { expect, type Locator, type Page, test } from "@playwright/test";
import { chooser } from "./chooser";
import { unfold } from "./folds";
import { askForRun, openReplay, stopRun } from "./replays";
import { selectAt } from "./view";

// How far, of 255, a colour of the panel may change for a label under it: a soft
// patch in the dark theme, 12 by this test; with no blur the words read, 22 and 30.
const LABEL_SHOWS_THROUGH = 16;

/** The largest change in any channel of any pixel between two screenshots of a size. */
function largestChange(page: Page, shots: [Buffer, Buffer]): Promise<number> {
  return page.evaluate(
    async (pngs) => {
      const pixels = await Promise.all(
        pngs.map(async (png) => {
          const bitmap = await createImageBitmap(
            await (await fetch(`data:image/png;base64,${png}`)).blob(),
          );
          const context = new OffscreenCanvas(bitmap.width, bitmap.height).getContext("2d");
          context?.drawImage(bitmap, 0, 0);
          return context?.getImageData(0, 0, bitmap.width, bitmap.height).data ?? [];
        }),
      );
      const [one = [], other = []] = pixels;
      let largest = 0;
      for (let i = 0; i < one.length; i++) {
        largest = Math.max(largest, Math.abs((one[i] ?? 0) - (other[i] ?? 0)));
      }
      return largest;
    },
    shots.map((shot) => shot.toString("base64")),
  );
}

/** The panel drawn with no label and with one in the middle of it, as the view
 * places one: inside the view's own element, which the panels lie over. */
async function withAndWithoutALabelUnder(panel: Locator): Promise<[Buffer, Buffer]> {
  const without = await panel.screenshot();
  await panel.evaluate((element) => {
    const { left, top, width, height } = element.getBoundingClientRect();
    const label = document.createElement("div");
    label.className = "debug-label";
    label.textContent = "wind 1.5 m/s from the SW";
    label.style.transform = `translate(${left + width / 2}px, ${top + height / 2}px)`;
    document.querySelector("[data-testid=main-view]")?.appendChild(label);
  });
  await expect(panel.page().locator(".debug-label")).toBeVisible();
  return [without, await panel.screenshot()];
}

for (const theme of ["dark", "light"]) {
  test(`a label under a panel does not read through it, ${theme}`, async ({ page }) => {
    await page.goto("/view");
    await expect(page.getByTestId("scene-status")).toHaveText("Showing the empty grid.");
    await page.getByLabel("Light panels").setChecked(theme === "light");
    const panel = page.locator(".info-panel");
    const shots = await withAndWithoutALabelUnder(panel);
    const change = await largestChange(page, shots);
    expect(change).toBeLessThanOrEqual(LABEL_SHOWS_THROUGH);
  });
}

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
    await unfold(page, "Display");
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
  await unfold(page, "Display");
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
  // The cards over the view too, the controls' as "What am I seeing?".
  await page.getByRole("button", { name: "Controls ?" }).click();
  expect(await background(".controls-help")).toBe("rgba(17, 24, 39, 0.9)");
  await page.getByRole("button", { name: "Close the controls" }).click();

  // Light, once chosen, and still so after a reload: from the panels' first
  // appearance, never flashing dark before.
  await page.getByRole("checkbox", { name: "Light panels" }).check();
  expect(await background(".info-panel")).toBe("rgba(255, 255, 255, 0.88)");
  await page.addInitScript(() => {
    new MutationObserver((_, observer) => {
      if (document.querySelector(".info-panel") !== null) {
        document.body.dataset.firstPanels = document.documentElement.dataset.theme ?? "dark";
        observer.disconnect();
      }
    }).observe(document, { childList: true, subtree: true });
  });
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Light panels" })).toBeChecked();
  await expect(page.locator("body")).toHaveAttribute("data-first-panels", "light");
  expect(await background(".info-panel")).toBe("rgba(255, 255, 255, 0.88)");
  await page.getByRole("checkbox", { name: "Light panels" }).uncheck();

  // A golden view's caption is light whatever the viewer's panels are.
  await page.goto("/qa/renderer?seed=42");
  expect(await background(".qa-caption")).toBe("rgba(255, 255, 255, 0.88)");
});

test("a page opens in its theme before its scripts run, never white in the dark one", async ({
  page,
}) => {
  // The page as the build serves it, before any of its scripts has run: they
  // are refused, and only the page, its inline script and its stylesheet load.
  await page.route(/\.(js|tsx?)(\?.*)?$/, (route) => route.abort());
  const opened = () =>
    page.evaluate(() => ({
      theme: document.documentElement.dataset.theme,
      // The browser draws the page's ground in this scheme until a page draws its own.
      scheme: getComputedStyle(document.documentElement).colorScheme,
      drawn: document.getElementById("root")?.childElementCount,
    }));

  await page.goto("/");
  expect(await opened()).toEqual({ theme: "dark", scheme: "dark", drawn: 0 });

  await page.evaluate(() => localStorage.setItem("greenhouse-sim.panels", "light"));
  await page.reload();
  expect(await opened()).toEqual({ theme: "light", scheme: "light", drawn: 0 });
  await page.evaluate(() => localStorage.removeItem("greenhouse-sim.panels"));
});

test("each side's panels fold to a stripe at the view's edge, and open as they were (#304)", async ({
  page,
}) => {
  // A scenario's sections in a short window: the info panel overflows.
  await page.setViewportSize({ width: 1280, height: 420 });
  await page.goto("/?scenario=climate_box");
  await expect(page.getByTestId("scene-status")).toContainText("climate_box", { timeout: 30_000 });
  await unfold(page, "Display");
  await unfold(page, "Weather");
  const info = page.locator(".info-panel");
  const hud = page.locator(".hud");
  const infoStripe = page.getByTestId("info-stripe");
  const viewStripe = page.getByTestId("view-stripe");
  // The info panel scrolled a little, to find it so again.
  await info.evaluate((panel) => {
    panel.scrollTop = 40;
  });
  const scrolled = await info.evaluate((panel) => panel.scrollTop);
  expect(scrolled).toBeGreaterThan(0);
  // Each stripe takes the height of the panel beside it, past its tab's (P22.9).
  const infoHeight = (await info.boundingBox())?.height ?? 0;
  expect(infoHeight).toBeGreaterThan(96);
  expect((await infoStripe.boundingBox())?.height).toBeCloseTo(infoHeight, 0);
  expect((await viewStripe.boundingBox())?.height).toBeCloseTo(
    Math.max(96, (await hud.boundingBox())?.height ?? 0),
    0,
  );

  await test.step("by the pointer, the info panel folds to its stripe at the left edge", async () => {
    await page.getByRole("button", { name: "Fold the info panel" }).click();
    await expect(info).toBeHidden();
    const stripe = await infoStripe.boundingBox();
    expect(stripe?.x).toBeLessThan(20);
    // Folded, nothing of the side but its stripe covers the view.
    expect(stripe?.width).toBeLessThan(20);
    // Folded, its stripe keeps the height of the panel beside it (P22.9).
    expect(stripe?.height).toBeCloseTo(infoHeight, 0);
    await expect(hud).toBeVisible();
  });

  await test.step("by the keyboard, the View panel folds to its stripe at the right edge", async () => {
    await page.getByRole("button", { name: "Fold the View panel" }).focus();
    await page.keyboard.press("Enter");
    await expect(hud).toBeHidden();
    const stripe = await viewStripe.boundingBox();
    expect((stripe?.x ?? 0) + (stripe?.width ?? 0)).toBeGreaterThan(1260);
  });

  await test.step("the view's controls, asked for by their key, open the View panel to be seen", async () => {
    await page.keyboard.press("?");
    await expect(page.getByRole("region", { name: "Moving around the view" })).toBeVisible();
    await expect(hud).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Fold the View panel" }).click();
    await expect(hud).toBeHidden();
  });

  await test.step("opened again, each is as it was, the info panel where it was scrolled", async () => {
    await page.getByRole("button", { name: "Open the info panel" }).press("Space");
    await page.getByRole("button", { name: "Open the View panel" }).click();
    await expect(info).toBeVisible();
    await expect(hud).toBeVisible();
    expect(await info.evaluate((panel) => panel.scrollTop)).toBe(scrolled);
  });

  await test.step("a docked, narrow window shows no stripe, and folds nothing", async () => {
    await page.getByRole("button", { name: "Fold the info panel" }).click();
    await page.setViewportSize({ width: 640, height: 480 });
    await expect(infoStripe).toBeHidden();
    await expect(info).toBeVisible();
  });
});

test("the View panel opens where it was, whatever changed while it was folded (#304)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene");
  const hud = page.locator(".hud");
  const putBack = page.getByRole("button", { name: "Put it back" });
  const hudLeft = async () => (await hud.boundingBox())?.x;
  // At the window's right edge, past its margin and with its stripe beside it.
  const leftAt = (width: number) => width - 12 - 324;
  await expect.poll(hudLeft).toBe(leftAt(1280));

  await test.step("the window resized", async () => {
    await page.getByRole("button", { name: "Fold the View panel" }).click();
    await expect(hud).toBeHidden();
    // Folded where it stands open, it still leaves the view there to be clicked.
    const underIt = await page.evaluate(
      ({ x, y }) => document.elementFromPoint(x, y)?.closest(".panel-column") ?? null,
      { x: leftAt(1280) + 100, y: 100 },
    );
    expect(underIt).toBeNull();
    await page.setViewportSize({ width: 1200, height: 720 });
    await page.getByRole("button", { name: "Open the View panel" }).click();
    await expect(hud).toBeVisible();
    await expect(putBack).toBeHidden();
    expect(await hudLeft()).toBe(leftAt(1200));
  });

  await test.step("the page reloaded, which measures the panel as it first draws", async () => {
    await page.getByRole("button", { name: "Fold the View panel" }).click();
    await expect(hud).toBeHidden();
    await page.reload();
    await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene");
    await page.getByRole("button", { name: "Open the View panel" }).click();
    await expect(hud).toBeVisible();
    await expect(putBack).toBeHidden();
    expect(await hudLeft()).toBe(leftAt(1200));
  });

  await test.step("its stripe, not covered by it, folds it again", async () => {
    await page.getByRole("button", { name: "Fold the View panel" }).click({ timeout: 5000 });
    await expect(hud).toBeHidden();
  });
});

test("a side's stripe stands at its panel's edge, however long a line of the panel (#304)", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1280, height: 720 });
  // In a replay, the notes that say what a stored run keeps are lines far
  // longer than the panel.
  const run = await askForRun(page, "climate_box", { seed: 63 });
  await openReplay(page, run);
  await expect(page.getByTestId("climate-time")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("replayed-checkpoints")).toBeVisible();
  const panel = await page.locator(".info-panel").boundingBox();
  const stripe = await page.getByTestId("info-stripe").boundingBox();
  const hud = await page.locator(".hud").boundingBox();
  const viewStripe = await page.getByTestId("view-stripe").boundingBox();

  expect((stripe?.x ?? 0) - ((panel?.x ?? 0) + (panel?.width ?? 0))).toBeLessThan(12);
  expect((hud?.x ?? 0) - ((viewStripe?.x ?? 0) + (viewStripe?.width ?? 0))).toBeLessThan(12);
  await stopRun(page, run);
});
