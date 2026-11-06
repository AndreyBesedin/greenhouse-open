import type { Locator } from "@playwright/test";

// WCAG 2.2's 1.4.3: words at 4.5:1 to what they are drawn on, large ones at 3:1.
export const TEXT_NEEDS = 4.5;
export const LARGE_TEXT_NEEDS = 3;

/** Each piece of text under `root` that falls short of its contrast, as "ratio:
 * element, its words": an element's own text, a field's value or its placeholder,
 * and the option a list shows. The ground is the elements' backgrounds behind it,
 * laid one over another on the browser's own (`Canvas`, by the page's
 * `color-scheme`), so that a translucent panel or a page with no ground of its own
 * is read as drawn. A
 * disabled control is left out, as WCAG leaves it; a background image or an
 * element's `opacity` is not read. */
export function lowContrast(root: Locator): Promise<string[]> {
  return root.evaluate(
    (top, [textNeeds, largeNeeds]) => {
      type Rgba = [number, number, number, number];
      const rgba = (written: string): Rgba => {
        const [red = 0, green = 0, blue = 0, alpha = 1] = (written.match(/[\d.]+/g) ?? []).map(
          Number,
        );
        return [red, green, blue, alpha];
      };
      const over = (above: Rgba, below: Rgba): Rgba => {
        const alpha = above[3];
        const mix = (part: number) => alpha * (above[part] ?? 0) + (1 - alpha) * (below[part] ?? 0);
        return [mix(0), mix(1), mix(2), 1];
      };
      const luminance = ([red, green, blue]: Rgba): number => {
        const linear = (level: number) => {
          const share = level / 255;
          return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
      };
      const ratio = (one: Rgba, other: Rgba): number => {
        const [low = 0, high = 0] = [luminance(one), luminance(other)].sort((a, b) => a - b);
        return (high + 0.05) / (low + 0.05);
      };

      const probe = document.createElement("div");
      probe.style.background = "Canvas";
      document.documentElement.append(probe);
      const canvas = rgba(getComputedStyle(probe).backgroundColor);
      probe.remove();
      const groundOf = (element: Element): Rgba => {
        const line: Element[] = [];
        for (let at: Element | null = element; at !== null; at = at.parentElement) {
          line.unshift(at);
        }
        return line.reduce(
          (ground, at) => over(rgba(getComputedStyle(at).backgroundColor), ground),
          canvas,
        );
      };
      const needs = (style: CSSStyleDeclaration): number => {
        const size = Number.parseFloat(style.fontSize);
        const bold = Number(style.fontWeight) >= 700;
        return size >= 24 || (bold && size >= 18.66) ? largeNeeds : textNeeds;
      };

      const short: string[] = [];
      const check = (element: Element, ink: string, words: string, style: CSSStyleDeclaration) => {
        const ground = groundOf(element);
        const contrast = ratio(over(rgba(ink), ground), ground);
        if (contrast < needs(style)) {
          const classes = element.getAttribute("class");
          const named = classes === null || classes === "" ? "" : `.${classes}`;
          short.push(`${contrast.toFixed(2)}: ${element.tagName.toLowerCase()}${named}, ${words}`);
        }
      };
      for (const element of [top, ...Array.from(top.querySelectorAll("*"))]) {
        const box = element.getBoundingClientRect();
        if (box.width === 0 || box.height === 0 || element.matches(":disabled")) {
          continue;
        }
        const style = getComputedStyle(element);
        if (style.visibility !== "visible") {
          continue;
        }
        const own = Array.from(element.childNodes)
          .filter((node) => node.nodeType === Node.TEXT_NODE)
          .map((node) => node.textContent ?? "")
          .join("")
          .trim();
        if (own !== "") {
          check(element, style.color, own, style);
        }
        if (element instanceof HTMLSelectElement) {
          const chosen = element.selectedOptions[0]?.textContent ?? "";
          if (chosen !== "") {
            check(element, style.color, chosen, style);
          }
        }
        if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
          if (element.value !== "") {
            check(element, style.color, element.value, style);
          } else if (element.placeholder !== "") {
            const placeholder = getComputedStyle(element, "::placeholder");
            const [red, green, blue, alpha] = rgba(placeholder.color);
            const faded = `rgba(${red}, ${green}, ${blue}, ${alpha * Number(placeholder.opacity)})`;
            check(element, faded, `placeholder "${element.placeholder}"`, style);
          }
        }
      }
      return short;
    },
    [TEXT_NEEDS, LARGE_TEXT_NEEDS] as const,
  );
}
