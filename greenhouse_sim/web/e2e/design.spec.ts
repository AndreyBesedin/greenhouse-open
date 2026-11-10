import { readFileSync } from "node:fs";

import { expect, type Locator, type Page, test } from "@playwright/test";
import type { Theme } from "../src/design/theme.ts";
import { designAddress } from "../src/qa/designPage.ts";
import { focusRing } from "./focusRing";

// The design system's reference page (P19.6), which needs no simulator: what a page
// reaches only with data is shown here, in each theme, for these checks and for its
// baselines (`visual/pages.spec.ts`).
const THEMES: readonly Theme[] = ["dark", "light"];
const TARGET_PX = 44;
const COMPACT_TARGET_PX = 24;
// Each control: a button, a disabled one, a link, and an icon of each, in every
// tone and size, and the one that shows the focus.
const COMPACT_CONTROLS = 3 * 5;
const CONTROLS = 2 * COMPACT_CONTROLS + 1;
const ENABLED = 2 * 3 * 3 + 1;
// Each field's control, one of them disabled, two compact (P19.9), and each fold's
// line (P19.7): drawn by the browser, as on the pages that use them, and a field's
// control as tall as its size asks.
const FIELDS = 7;
const COMPACT_FIELDS = 2;
const FOLDS = 2;
// A radius this large is cut down to half its box, so that a pixel moves nothing:
// what shows is that it is drawn at all.
const MOVED_BY_MORE: Readonly<Record<string, string>> = { "--radius-pill": "1px" };
const TOKENS = [
  ...new Set(
    readFileSync(new URL("../src/design/tokens.css", import.meta.url), "utf8").match(
      /--[\w-]+(?=\s*:)/g,
    ),
  ),
];

function controls(page: Page): Locator {
  return page.locator("main").locator("button, a");
}

function fieldsAndFolds(page: Page): Locator {
  return page.locator("main").locator("input, select, summary");
}

function fieldControls(page: Page): Locator {
  return page.locator("main").locator("input, select");
}

/** `written`, the value of a token, changed by the least that can show. */
function movedByTheLeast(name: string, written: string): string {
  const more = MOVED_BY_MORE[name];
  if (more !== undefined) {
    return more;
  }
  if (name === "--scheme") {
    return written === "dark" ? "light" : "dark";
  }
  const pixels = /^(\d+)px$/.exec(written);
  if (pixels !== null) {
    return `${Number(pixels[1]) + 1}px`;
  }
  // The build writes a colour in hex, as short as it can: one level of blue, on the
  // side that stays in range.
  if (!/^#[0-9a-f]+$/i.test(written)) {
    throw new Error(`${name}: no way to move ${written}`);
  }
  const hex = written.length > 5 ? written : written.replace(/[0-9a-f]/gi, "$&$&");
  const blue = Number.parseInt(hex.slice(5, 7), 16);
  const moved = (blue === 0 ? 1 : blue - 1).toString(16).padStart(2, "0");
  return `${hex.slice(0, 5)}${moved}${hex.slice(7)}`;
}

for (const theme of THEMES) {
  test.describe(`the reference page, ${theme}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.goto(designAddress(theme));
      await expect(controls(page)).toHaveCount(CONTROLS);
    });

    test("takes its theme from its address, and leaves a person's choice alone", async ({
      page,
    }) => {
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      expect(await page.evaluate(() => localStorage.length)).toBe(0);
    });

    test("names every control", async ({ page }) => {
      await expect(fieldsAndFolds(page)).toHaveCount(FIELDS + FOLDS);
      for (const control of [
        ...(await controls(page).all()),
        ...(await fieldsAndFolds(page).all()),
      ]) {
        await expect(control).toHaveAccessibleName(/\S/);
      }
    });

    test("names a field's control by its label, and describes it by its hint and problem", async ({
      page,
    }) => {
      const refused = page.getByRole("textbox", { name: "a field, with a problem", exact: true });
      await expect(refused).toHaveAccessibleDescription("what it takes why it is refused");
      await expect(refused).toHaveAttribute("aria-invalid", "true");
      const hinted = page.getByRole("textbox", { name: "a field, with a hint", exact: true });
      await expect(hinted).toHaveAccessibleDescription("what it takes");
      await expect(hinted).not.toHaveAttribute("aria-invalid");
      await expect(page.getByRole("combobox", { name: "a choice", exact: true })).toBeVisible();
    });

    test("says each status and notice in words, and each notice in its role", async ({ page }) => {
      await expect(page.locator("main .ds-status-chip")).toHaveText([
        "plain",
        "active",
        "problem",
        "problem, with a note what it means",
      ]);
      await expect(page.getByRole("alert")).toHaveText("a problem");
      await expect(page.getByRole("status")).toHaveText("a status");
    });

    test("gives every control its target, measured", async ({ page }) => {
      let compact = 0;
      for (const control of await controls(page).all()) {
        const box = await control.boundingBox();
        const isCompact = await control.evaluate((element) =>
          element.classList.contains("ds-button-compact"),
        );
        compact += isCompact ? 1 : 0;
        const least = isCompact ? COMPACT_TARGET_PX : TARGET_PX;
        const name = (await control.getAttribute("aria-label")) ?? (await control.textContent());
        expect(box?.height ?? 0, name ?? "").toBeGreaterThanOrEqual(least);
        expect(box?.width ?? 0, name ?? "").toBeGreaterThanOrEqual(least);
      }
      expect(compact).toBe(COMPACT_CONTROLS);
    });

    test("gives every field's control its height, measured", async ({ page }) => {
      await expect(fieldControls(page)).toHaveCount(FIELDS);
      let compact = 0;
      for (const control of await fieldControls(page).all()) {
        const box = await control.boundingBox();
        const isCompact = await control.evaluate((element) =>
          element.classList.contains("ds-field-control-compact"),
        );
        compact += isCompact ? 1 : 0;
        const name = (await control.getAttribute("id")) ?? "";
        expect(box?.height ?? 0, name).toBeGreaterThanOrEqual(
          isCompact ? COMPACT_TARGET_PX : TARGET_PX,
        );
      }
      expect(compact).toBe(COMPACT_FIELDS);
    });

    test("draws every component in the weight its words are read in", async ({ page }) => {
      // A change of weight alone may not show in the pinned container's images.
      const weights = await page
        .locator("main")
        .locator("button, a, .ds-status-chip, .ds-field > label")
        .evaluateAll((all) => [
          ...new Set(all.map((element) => getComputedStyle(element).fontWeight)),
        ]);
      expect(weights).toEqual(["600"]);
    });

    test("draws the page again when any token moves by the least", async ({ page }) => {
      test.setTimeout(120_000);
      // After two frames: a picture taken sooner can be the one before the change.
      const drawn = async () => {
        await page.evaluate(
          () => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))),
        );
        return page.screenshot({ fullPage: true, animations: "disabled" });
      };
      expect((await drawn()).equals(await drawn()), "the page is not still").toBe(true);

      const seesNothing: string[] = [];
      for (const name of TOKENS) {
        const written = await page.evaluate(
          (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim(),
          name,
        );
        const moved = movedByTheLeast(name, written);
        // Compared with the picture just before: text drawn again in the same colour,
        // once it has been another, need not be the same to the pixel.
        const before = await drawn();
        await page.evaluate(
          ([token, value]) =>
            document.documentElement.style.setProperty(token as string, value as string),
          [name, moved],
        );
        if ((await drawn()).equals(before)) {
          seesNothing.push(`${name}: ${written} to ${moved}`);
        }
        await page.evaluate((token) => document.documentElement.style.removeProperty(token), name);
      }
      expect(seesNothing).toEqual([]);
    });
  });
}

test.describe("a component, by keyboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(designAddress("dark"));
    await expect(controls(page)).toHaveCount(CONTROLS);
  });

  /** Counts what activates `control`, without following it. */
  async function countingPresses(control: Locator): Promise<void> {
    await control.evaluate((element) => {
      element.addEventListener("click", (event) => {
        event.preventDefault();
        element.dataset.pressed = String(Number(element.dataset.pressed ?? 0) + 1);
      });
    });
  }

  test("reaches each one that is enabled, in order, and passes over the disabled", async ({
    page,
  }) => {
    const enabled = page
      .locator("main")
      .locator("button:enabled, a, input:enabled, select:enabled, summary");
    await expect(enabled).toHaveCount(ENABLED + FIELDS - 1 + FOLDS);
    // The page opens on its first control, which shows the focus.
    await expect(enabled.first()).toBeFocused();
    for (const control of (await enabled.all()).slice(1)) {
      await page.keyboard.press("Tab");
      await expect(control).toBeFocused();
    }
  });

  test("presses a button with Enter and with Space, and a disabled one not at all", async ({
    page,
  }) => {
    const button = page.getByRole("button", { name: "plain target", exact: true });
    await countingPresses(button);
    await button.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Space");
    await expect(button).toHaveAttribute("data-pressed", "2");

    const icon = page.getByRole("button", { name: "plain target, an icon", exact: true });
    await countingPresses(icon);
    await icon.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Space");
    await expect(icon).toHaveAttribute("data-pressed", "2");

    const disabled = page.getByRole("button", { name: "plain target, disabled", exact: true });
    await expect(disabled).toBeDisabled();
    await countingPresses(disabled);
    await disabled.click({ force: true });
    await disabled.evaluate((element) => (element as HTMLElement).focus());
    await expect(disabled).not.toBeFocused();
    await expect(disabled).not.toHaveAttribute("data-pressed");
  });

  test("opens and folds a fold by its line, with Enter", async ({ page }) => {
    const held = page.getByText("what it holds, folded", { exact: true });
    await expect(held).toBeHidden();
    await page.getByText("folded", { exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(held).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(held).toBeHidden();
    await expect(page.getByText("what it holds", { exact: true })).toBeVisible();
  });

  test("follows a link with Enter, and not with Space, as any link", async ({ page }) => {
    const link = page.getByRole("link", { name: "plain target, a link", exact: true });
    await countingPresses(link);
    await link.focus();
    await page.keyboard.press("Space");
    await expect(link).not.toHaveAttribute("data-pressed");
    await page.keyboard.press("Enter");
    await expect(link).toHaveAttribute("data-pressed", "1");
  });

  test("shows the ring on keyboard focus, in the tokens' sizes, and none on a click", async ({
    page,
  }) => {
    const outline = (control: Locator) =>
      control.evaluate((element) => {
        const style = getComputedStyle(element);
        return [style.outlineStyle, style.outlineWidth, style.outlineOffset].join(" ");
      });

    const shown = page.getByRole("button", { name: "focused", exact: true });
    await expect(shown).toBeFocused();
    expect(await outline(shown)).toBe("solid 3px 2px");

    const clicked = page.getByRole("button", { name: "plain target", exact: true });
    await clicked.click();
    await expect(clicked).toBeFocused();
    expect(await outline(clicked)).not.toContain("solid");

    await page.keyboard.press("Tab");
    expect(await outline(page.locator(":focus"))).toBe("solid 3px 2px");
  });

  test("draws the one ring, in --action, on every kind of control the keyboard reaches", async ({
    page,
  }) => {
    // A button, a link, a field's input and select, and a fold's line (P19.12): each
    // was drawn by the browser's own ring but the buttons.
    const enabled = page
      .locator("main")
      .locator("button:enabled, a, input:enabled, select:enabled, summary");
    const kinds = new Set<string>();
    for (let tab = 0; tab < (await enabled.count()); tab += 1) {
      const focused = page.locator(":focus");
      const kind = await focused.evaluate((element) => element.tagName.toLowerCase());
      kinds.add(kind);
      expect(await focusRing(focused), kind).toBe("solid 3px 2px --action");
      await page.keyboard.press("Tab");
    }
    expect([...kinds].sort()).toEqual(["a", "button", "input", "select", "summary"]);
  });
});
