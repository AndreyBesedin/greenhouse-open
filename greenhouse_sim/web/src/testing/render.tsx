import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";

export interface Rendered {
  /** What it draws, to find its parts in as a person would. */
  container: HTMLElement;
  /** Draws it again, with other props. */
  rerender(element: ReactNode): void;
  unmount(): void;
}

/**
 * Mounts a component, for tests in a DOM environment
 * (`// @vitest-environment jsdom`), so that its controls are used as a person
 * uses them and its handlers run: unlike its static markup, which neither
 * clicks nor changes anything.
 */
export function render(element: ReactNode): Rendered {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  act(() => root.render(element));
  return {
    container,
    rerender(next) {
      act(() => root.render(next));
    },
    unmount() {
      act(() => root.unmount());
      container.remove();
    },
  };
}

/** The button whose text, or label, is `name`. */
export function button(within: ParentNode, name: string): HTMLButtonElement {
  const found = [...within.querySelectorAll("button")].filter(
    (candidate) => (candidate.getAttribute("aria-label") ?? candidate.textContent?.trim()) === name,
  );
  return only(found, `a button named "${name}"`);
}

/** The select labelled `name`, by its label or the label around it. */
export function select(within: ParentNode, name: string): HTMLSelectElement {
  const found = [...within.querySelectorAll("select")].filter(
    (candidate) =>
      candidate.getAttribute("aria-label") === name ||
      candidate.closest("label")?.firstChild?.textContent?.trim() === name,
  );
  return only(found, `a select labelled "${name}"`);
}

/** What the element with this test id says, or null if there is none. */
export function said(within: ParentNode, testId: string): string | null {
  return within.querySelector(`[data-testid="${testId}"]`)?.textContent ?? null;
}

/** Clicks a control, as a person would. */
export function click(control: HTMLElement): void {
  act(() => control.click());
}

/** Chooses one of a select's options, by its value, as a person would. */
export function choose(control: HTMLSelectElement, value: string): void {
  act(() => {
    control.value = value;
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function only<T>(found: T[], what: string): T {
  const [first, ...more] = found;
  if (first === undefined || more.length > 0) {
    throw new Error(`expected one of ${what}, found ${found.length}`);
  }
  return first;
}
