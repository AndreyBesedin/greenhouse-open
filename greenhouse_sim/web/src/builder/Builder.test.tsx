// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { button, click, enter, type Rendered, render, said } from "../testing/render";
import { Builder } from "./Builder";

// The simulator's first draft of the form's starting house, as it answers it.
const STARTING_HOUSE = JSON.parse(
  readFileSync(join(process.cwd(), "src/builder/testing/startingHouse.json"), "utf8"),
);

function answer(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

/** A simulator whose saves are held until `release` is called, and which
 * draws no house, so that no WebGL is asked for. */
function holdingSaves(): { release: () => void } {
  let release = () => {};
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/builder/basic") || url.startsWith("/api/builder/assess")) {
      return answer(STARTING_HOUSE);
    }
    if (url.includes("/save")) {
      const { schema_version, ...installation } = JSON.parse(String(init?.body));
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return answer({
        draft_id: installation.installation_id,
        revision: 1,
        saved_at: "2026-10-23T12:00:00Z",
        schema_version,
        installation,
        findings: [],
      });
    }
    if (url.startsWith("/api/drafts")) {
      return answer([]);
    }
    return answer({ error: "not here" }, 404);
  });
  return {
    release: () => release(),
  };
}

async function settled(): Promise<void> {
  await act(async () => {
    for (let turn = 0; turn < 20; turn += 1) {
      await Promise.resolve();
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function rows(within: HTMLElement): string[] {
  return [...within.querySelectorAll(".builder-rows tbody tr")].map((row) => row.textContent ?? "");
}

function give(within: HTMLElement, row: number, variety: string): void {
  const box = within.querySelector<HTMLInputElement>(`[aria-label="Choose row ${row}"]`);
  if (box === null) {
    throw new Error(`no row ${row}`);
  }
  click(box);
  enter(within.querySelector(".builder-give input") as HTMLInputElement, variety);
  click(button(within, "Give the chosen rows this crop"));
  click(box);
}

describe("the setup builder (P12.2)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps an edit made while a save is on its way, as changed since", async () => {
    const saves = holdingSaves();
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();
    give(page, 2, "beefsteak");

    click(button(page, "Save"));
    await settled();
    // Not saved twice over while the first is on its way.
    expect(button(page, "Save").disabled).toBe(true);
    give(page, 1, "roma");
    saves.release();
    await settled();

    expect(rows(page)).toEqual(["1simpleroma", "2simplebeefsteak"]);
    expect(said(page, "builder-status")).toBe("Saved as revision 1.");
    expect(said(page, "builder-draft")).toBe(
      "My greenhouse (my_greenhouse), revision 1, changed since",
    );
    expect(button(page, "Undo").disabled).toBe(false);
  });

  it("drops a save's answer that arrives once the draft is left", async () => {
    const saves = holdingSaves();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save"));
    await settled();
    click(button(page, "Start again"));
    saves.release();
    await settled();

    expect(said(page, "builder-draft")).toBeNull();
    expect(said(page, "builder-status")).toBe("");
    expect(page.querySelector(".builder-form")).not.toBeNull();
  });

  it("asks before leaving what is not saved", async () => {
    holdingSaves();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Start again"));

    expect(confirm).toHaveBeenCalledOnce();
    expect(said(page, "builder-draft")).toBe("My greenhouse (my_greenhouse), not saved");
  });
});
