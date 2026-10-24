// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { button, choose, click, enter, type Rendered, render, said } from "../testing/render";
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
        schema_version,
        installation,
        findings: [],
        draft: {
          draft_id: installation.installation_id,
          revision: 1,
          saved_at: "2026-10-23T12:00:00Z",
        },
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

/** A simulator whose edits of many items are held until `release` is
 * called, each answering the house it was sent with one heater more. */
function holdingEdits(): { release: () => void } {
  let release = () => {};
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/builder/basic") || url.startsWith("/api/builder/assess")) {
      return answer(STARTING_HOUSE);
    }
    if (url.startsWith("/api/builder/edit")) {
      const { file } = JSON.parse(String(init?.body));
      const { schema_version, ...installation } = file;
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      const heater = {
        actuator_id: "heater_1",
        // As the simulator answers it: every field, its defaults too.
        heading: 0,
        kind: "heater",
        base: { x: 1, y: 1, z: 0 },
        size_x: 0.6,
        size_y: 0.8,
        size_z: 1.2,
        power_w: 10_000,
      };
      const layout = { ...installation.layout, equipment: [heater] };
      return answer({ schema_version, installation: { ...installation, layout }, findings: [] });
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

function placeAHeater(within: HTMLElement): void {
  const what = within.querySelector<HTMLSelectElement>(".builder-palette select");
  if (what === null) {
    throw new Error("no palette");
  }
  choose(what, "heater");
  click(button(within, "Place"));
}

function items(within: HTMLElement): string[] {
  return [...within.querySelectorAll(".builder-items tbody tr td:nth-child(2)")].map(
    (cell) => cell.textContent ?? "",
  );
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
  enter(within.querySelector(".builder-rows .builder-give input") as HTMLInputElement, variety);
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

  it("keeps an edit of many items the simulator made as one step to undo (P12.3)", async () => {
    const edits = holdingEdits();
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    placeAHeater(page);
    edits.release();
    await settled();

    expect(items(page)).toEqual(["heater_1"]);
    expect(said(page, "builder-status")).toBe("Placed 1 heater.");
    click(button(page, "Undo"));
    expect(items(page)).toEqual([]);
  });

  it("drops an edit of many items answered once the draft changed, losing no edit (P12.3)", async () => {
    const edits = holdingEdits();
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    placeAHeater(page);
    await settled();
    give(page, 1, "roma");
    edits.release();
    await settled();

    expect(items(page)).toEqual([]);
    expect(rows(page)[0]).toBe("1simpleroma");
    expect(said(page, "builder-status")).toBe(
      "The draft changed while that edit was on its way: make it again.",
    );
  });

  it("exports a draft only once the edit under way is made, with it (P12.3)", async () => {
    const edits = holdingEdits();
    const exported: Blob[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((file) => {
      exported.push(file as Blob);
      return "blob:exported";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    placeAHeater(page);
    await settled();
    expect(button(page, "Export").disabled).toBe(true);
    click(button(page, "Export"));
    expect(exported).toEqual([]);

    edits.release();
    await settled();
    click(button(page, "Export"));
    const [file] = exported;
    expect(exported).toHaveLength(1);
    expect(JSON.parse(await (file as Blob).text()).layout.equipment).toMatchObject([
      { actuator_id: "heater_1" },
    ]);
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

  it("says why no scenario's house can be copied, and lists them again when asked", async () => {
    const asked: string[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      asked.push(url);
      return url.startsWith("/api/drafts") ? answer([]) : answer({ error: "busy" }, 503);
    });
    shown = render(<Builder />);
    const page = shown.container;
    await settled();

    expect(said(page, "builder-scenarios")).toBe(
      "The scenarios cannot be listed: the simulator API answered 503",
    );
    click(button(page, "List the scenarios again"));
    await settled();
    expect(asked.filter((url) => url.startsWith("/api/scenarios"))).toHaveLength(2);
  });
});
