// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { button, click, type Rendered, render } from "../testing/render";
import { UploadScenario } from "./UploadScenario";
import { keptFields } from "./uploaded";

// The fields the page reads of what the simulator answers an upload of the Climate box's file under another
// identifier.
const UPLOADED = JSON.parse(
  readFileSync(join(process.cwd(), "src/landing/testing/uploadedScenario.json"), "utf8"),
);

function stubSimulator(answer: Response): string[] {
  const bodies: string[] = [];
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
    bodies.push(String(init?.body));
    return answer;
  });
  return bodies;
}

/** A file chosen in the control, as a person chooses one. */
async function choose(page: HTMLElement, name: string, text: string): Promise<void> {
  const input = page.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) {
    throw new Error("no file control");
  }
  const picked = new File([text], name, { type: "application/json" });
  Object.defineProperty(input, "files", { value: [picked], configurable: true });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
    for (let turn = 0; turn < 20; turn += 1) {
      await Promise.resolve();
    }
  });
}

describe("a scenario file uploaded from the start page (P17.11)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("opens in the builder, with the run settings its file held, and starts no run", async () => {
    const bodies = stubSimulator(new Response(JSON.stringify(UPLOADED)));
    const went: string[] = [];
    shown = render(<UploadScenario navigate={(address) => went.push(address)} />);

    await choose(shown.container, "shared.scenario.json", '{"greenhouse_id":"shared_box"}');

    expect(bodies).toEqual(['{"greenhouse_id":"shared_box"}']);
    expect(went).toEqual(["/builder#scenario=shared_box"]);
    expect(keptFields("shared_box")).toMatchObject({
      days: String(UPLOADED.settings.duration_days),
      seed: String(UPLOADED.settings.random_seed),
    });
  });

  it("says a refusal next to the control, naming the file, and goes nowhere", async () => {
    stubSimulator(
      new Response(JSON.stringify({ error: "'climate_box' is a packaged scenario's" }), {
        status: 409,
      }),
    );
    const went: string[] = [];
    shown = render(<UploadScenario navigate={(address) => went.push(address)} />);

    await choose(shown.container, "climate.scenario.json", "{}");

    expect(shown.container.querySelector('[role="alert"]')?.textContent).toBe(
      "climate.scenario.json cannot be opened: 'climate_box' is a packaged scenario's",
    );
    expect(went).toEqual([]);
  });

  it("asks for the file with its recorded weather when this simulator does not have it", async () => {
    stubSimulator(
      new Response(
        JSON.stringify({
          ...UPLOADED,
          scenario: null,
          kept: false,
          missing_weather: { file: "spring.csv", digest: "ab".repeat(32) },
        }),
      ),
    );
    const went: string[] = [];
    shown = render(<UploadScenario navigate={(address) => went.push(address)} />);

    await choose(shown.container, "shared.scenario.json", "{}");

    expect(shown.container.querySelector('[role="alert"]')?.textContent).toContain(
      "runs under spring.csv, which it does not carry",
    );
    expect(went).toEqual([]);
  });

  it("is a button a person can reach, described by what it does", () => {
    shown = render(<UploadScenario navigate={() => {}} />);
    const upload = button(shown.container, "Upload a scenario file");
    const hint = shown.container.querySelector(`#${upload.getAttribute("aria-describedby")}`);

    expect(hint?.textContent).toContain("opens in the builder");
    const pick = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    click(upload);
    expect(pick).toHaveBeenCalledOnce();
  });
});
