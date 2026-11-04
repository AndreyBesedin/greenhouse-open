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

const SCENARIO = {
  id: "my_greenhouse_run",
  name: "My greenhouse",
  description: "",
  plants: 3,
  duration_days: 30,
  crop_model: "simple",
  daily: [],
  openings: [],
  opening_day: null,
  layouts: ["default"],
  weathers: ["default"],
  thermostat: null,
};

// The run a worker is asked for: an epoch queued.
const STARTED = {
  run_id: "my_greenhouse_run-climate-abc",
  epoch: 2,
  scenario_id: "my_greenhouse_run",
  seed: null,
  layout: "default",
  status: "queued",
  paused: false,
  frontier_s: 0,
  duration_s: 86400,
  progress: 0,
  created_at: null,
  size_bytes: 0,
  start_s: 0,
  fork: null,
  stopping: false,
  damaged: false,
  days_computed: 0,
  cpu_s: null,
  peak_memory_bytes: null,
  reason: null,
};

/** A simulator that saves, runs a draft as a scenario and starts its run;
 * every request is kept, as its method and address with the body. */
function runningDrafts(
  starts: Response = answer(STARTED),
  registering: Promise<unknown> = Promise.resolve(),
): string[] {
  const asked: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    asked.push(`${init?.method ?? "GET"} ${url} ${init?.body ?? ""}`.trim());
    if (url.startsWith("/api/builder/basic") || url.startsWith("/api/builder/assess")) {
      return answer(STARTING_HOUSE);
    }
    if (url.includes("/save")) {
      const { schema_version, ...installation } = JSON.parse(String(init?.body));
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
    if (url.includes("/run?")) {
      await registering;
      return answer(SCENARIO);
    }
    if (url.endsWith("/runs?seconds_per_day=10") && init?.method === "POST") {
      return starts;
    }
    if (url.startsWith("/api/drafts") || url.startsWith("/api/scenarios")) {
      return answer(url.startsWith("/api/scenarios") ? [SCENARIO] : []);
    }
    return answer({ error: "not here" }, 404);
  });
  return asked;
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
  it("saves the draft and goes back to the start page (P17.11)", async () => {
    const asked = runningDrafts();
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save and go back"));
    await settled();

    expect(asked.filter((each) => each.includes("/save"))).toHaveLength(1);
    expect(went).toEqual(["/"]);
  });

  it("goes back without saving again what is saved (P17.11)", async () => {
    const asked = runningDrafts();
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();
    click(button(page, "Save"));
    await settled();

    click(button(page, "Save and go back"));
    await settled();

    expect(asked.filter((each) => each.includes("/save"))).toHaveLength(1);
    expect(went).toEqual(["/"]);
  });

  it("saves, runs the draft under the run step's settings and follows the run started (P17.11)", async () => {
    const asked = runningDrafts();
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();
    const days = page.querySelector<HTMLInputElement>('.builder-run input[type="number"]');
    enter(days as HTMLInputElement, "30");

    click(button(page, "Save and start a run"));
    await settled();

    const ran = asked.find((each) => each.includes("/run?"));
    expect(ran).toContain("POST /api/drafts/my_greenhouse/run?revision=1");
    expect(JSON.parse(ran?.split("revision=1 ")[1] ?? "{}")).toMatchObject({
      start_date: "2026-04-01",
      duration_days: 30,
      random_seed: 0,
    });
    expect(
      asked.some((each) => each.startsWith("POST /api/scenarios/my_greenhouse_run/runs?")),
    ).toBe(true);
    expect(went).toEqual(["/replay?run=my_greenhouse_run-climate-abc&epoch=2&follow=1"]);
  });

  it("says that the run was registered and not started when the simulator refuses to start it (P17.11)", async () => {
    runningDrafts(answer({ error: "no room for another run" }, 409));
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save and start a run"));
    await settled();

    expect(went).toEqual([]);
    expect(said(page, "builder-status")).toContain(
      "registered as my_greenhouse_run, but not started: no room for another run",
    );
  });

  it("keeps the run step's settings through edits, and forgets them with the draft (P17.11)", async () => {
    runningDrafts();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();
    const days = () => page.querySelector<HTMLInputElement>('.builder-run input[type="number"]');
    enter(days() as HTMLInputElement, "45");

    give(page, 1, "roma");
    expect(days()?.value).toBe("45");

    click(button(page, "Start again"));
    click(button(page, "Draft this house"));
    await settled();
    expect(days()?.value).toBe("7");
  });

  it("offers the scenario's file once the draft is run as a scenario (P17.11)", async () => {
    runningDrafts();
    shown = render(<Builder />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();
    expect(page.querySelector(".builder-share")).toBeNull();

    click(button(page, "Save"));
    await settled();
    click(button(page, "Run this revision"));
    await settled();

    expect(page.querySelector(".builder-share")).not.toBeNull();
    expect(button(page, "Download scenario file")).toBeDefined();
  });

  it("opens an uploaded scenario's house as a draft not saved, with the run settings its file held (P17.11)", async () => {
    sessionStorage.setItem(
      "greenhouse.uploaded.shared_box",
      JSON.stringify({
        start_date: "2026-03-01",
        duration_days: 12,
        random_seed: 3,
        weather: "default",
      }),
    );
    const asked: string[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      asked.push(url);
      if (
        url === "/api/scenarios/shared_box/installation" ||
        url.startsWith("/api/builder/assess")
      ) {
        return answer(STARTING_HOUSE);
      }
      return answer(
        url.startsWith("/api/drafts") || url === "/api/scenarios" ? [] : { error: "no" },
        200,
      );
    });
    shown = render(<Builder hash="#scenario=shared_box" />);
    const page = shown.container;
    await settled();

    expect(asked).toContain("/api/scenarios/shared_box/installation");
    expect(said(page, "builder-status")).toBe(
      "Opened My greenhouse from a scenario file; not saved yet.",
    );
    expect(said(page, "builder-draft")).toBe("My greenhouse (my_greenhouse), not saved");
    const fields = [...page.querySelectorAll<HTMLInputElement>(".builder-run input")].map(
      (input) => input.value,
    );
    expect(fields).toEqual(["2026-03-01", "12", "3"]);
    // A run made of the draft keeps the file's weather and site by its name alone,
    // and the file's own can be run as it is.
    expect(said(page, "builder-uploaded-note")).toContain("opened from a scenario file");
    expect(said(page, "builder-uploaded-note")).toContain(
      "While its identifier is the file's, a run made here keeps the file's weather and site",
    );
    expect(said(page, "builder-uploaded-note")).toContain(
      "Given another identifier, it runs under the default weather and site",
    );
    expect(
      page.querySelector('[data-testid="builder-uploaded-note"] a')?.getAttribute("href"),
    ).toBe("/#run=shared_box");
    sessionStorage.clear();
  });

  it("says why an uploaded scenario cannot be opened, and shows the first form (P17.11)", async () => {
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      return url.includes("/installation")
        ? answer({ error: "no such scenario" }, 404)
        : answer(
            url.startsWith("/api/drafts") ? [] : { error: "no" },
            url.startsWith("/api/drafts") ? 200 : 404,
          );
    });
    shown = render(<Builder hash="#scenario=gone" />);
    await settled();

    expect(said(shown.container, "builder-status")).toBe(
      "The uploaded scenario cannot be opened: no such scenario",
    );
    expect(shown.container.querySelector(".builder-form")).not.toBeNull();
  });

  it("does not leave with an edit made while the save was on its way (P17.11)", async () => {
    const saves = holdingSaves();
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save and go back"));
    await settled();
    give(page, 1, "roma");
    saves.release();
    await settled();

    expect(went).toEqual([]);
    expect(said(page, "builder-status")).toBe(
      "The draft changed while it was being saved: save it again before leaving.",
    );
    expect(said(page, "builder-draft")).toBe(
      "My greenhouse (my_greenhouse), revision 1, changed since",
    );
  });

  it("does not run a house that changed while it was being saved (P17.11)", async () => {
    const saves = holdingSaves();
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save and start a run"));
    await settled();
    give(page, 1, "roma");
    saves.release();
    await settled();

    expect(went).toEqual([]);
    expect(said(page, "builder-status")).toBe(
      "The draft changed while it was being saved: save it again to run it.",
    );
  });

  it("starts no run for a draft left while it was being registered (P17.11)", async () => {
    let registered = () => {};
    const asked = runningDrafts(
      answer(STARTED),
      new Promise((resolve) => {
        registered = () => resolve(undefined);
      }),
    );
    const went: string[] = [];
    shown = render(<Builder navigate={(address) => went.push(address)} />);
    const page = shown.container;
    await settled();
    click(button(page, "Draft this house"));
    await settled();

    click(button(page, "Save and start a run"));
    await settled();
    click(button(page, "Start again"));
    registered();
    await settled();

    expect(asked.some((each) => each.includes("/runs?"))).toBe(false);
    expect(went).toEqual([]);
    expect(said(shown.container, "builder-status")).toBe("");
  });
  it("keeps the run settings of the draft opened while an uploaded scenario was on its way (P17.11)", async () => {
    sessionStorage.setItem(
      "greenhouse.uploaded.shared_box",
      JSON.stringify({
        start_date: "2026-03-01",
        duration_days: 12,
        random_seed: 3,
        weather: "default",
      }),
    );
    let arrives = () => {};
    const slow = new Promise<void>((resolve) => {
      arrives = resolve;
    });
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/scenarios/shared_box/installation") {
        await slow;
        return answer(STARTING_HOUSE);
      }
      if (url.startsWith("/api/builder/assess")) {
        return answer(STARTING_HOUSE);
      }
      return answer(
        url.startsWith("/api/drafts") || url === "/api/scenarios" ? [] : { error: "no" },
      );
    });
    shown = render(<Builder hash="#scenario=shared_box" />);
    const page = shown.container;
    await settled();

    // A file imported while the scenario is on its way.
    const input = page.querySelector<HTMLInputElement>(".builder-start input[type=file]");
    Object.defineProperty(input, "files", {
      value: [new File(["{}"], "mine.json", { type: "application/json" })],
      configurable: true,
    });
    await act(async () => {
      input?.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await settled();
    arrives();
    await settled();

    expect(said(page, "builder-status")).toContain("Imported");
    const fields = [...page.querySelectorAll<HTMLInputElement>(".builder-run input")].map(
      (each) => each.value,
    );
    expect(fields).toEqual(["2026-04-01", "7", "0"]);
    expect(page.querySelector('[data-testid="builder-uploaded-note"]')).toBeNull();
    sessionStorage.clear();
  });
});
