// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { button, checkbox, click, type Rendered, render } from "../testing/render";
import { ShareScenario } from "./ShareScenario";

const WHOLE = JSON.stringify({ scenario: "x", recorded_weather: { csv: "a".repeat(5000) } });
const BARE = JSON.stringify({ scenario: "x" });

function download(text: string, hasRecording: boolean) {
  return { file_name: "x.scenario.json", text, has_recording: hasRecording };
}

/** The simulator, stood in for: the file of a scenario with a recorded
 * weather, whole and without it, or one with none. */
function serving(recorded: boolean): string[] {
  const asked: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    const url = String(input);
    asked.push(url);
    if (url.endsWith("/file?recording=0")) {
      return new Response(JSON.stringify(download(BARE, false)));
    }
    if (url.endsWith("/file")) {
      return new Response(JSON.stringify(download(recorded ? WHOLE : BARE, recorded)));
    }
    return new Response(JSON.stringify({ error: "not here" }), { status: 404 });
  });
  return asked;
}

async function settled(): Promise<void> {
  await act(async () => {
    for (let turn = 0; turn < 20; turn += 1) {
      await Promise.resolve();
    }
  });
}

/** What the page was offered for download, as text. */
function offered(): Promise<string>[] {
  const files: Promise<string>[] = [];
  vi.spyOn(URL, "createObjectURL").mockImplementation((file) => {
    files.push((file as Blob).text());
    return "blob:offered";
  });
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return files;
}

describe("a scenario handed on as a file (P17.11)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("downloads the file with its recorded weather, and says what the weather adds", async () => {
    serving(true);
    const files = offered();
    shown = render(<ShareScenario scenarioId="x" />);
    await settled();

    const include = checkbox(shown.container, "Include the recorded weather (5 kB)");
    expect(include.checked).toBe(true);
    click(button(shown.container, "Download scenario file"));

    expect(await Promise.all(files)).toEqual([WHOLE]);
  });

  it("downloads the file without the recorded weather when it is left out", async () => {
    serving(true);
    const files = offered();
    shown = render(<ShareScenario scenarioId="x" />);
    await settled();

    click(checkbox(shown.container, "Include the recorded weather (5 kB)"));
    click(button(shown.container, "Download scenario file"));

    expect(await Promise.all(files)).toEqual([BARE]);
  });

  it("asks nothing about the weather of a scenario that has none recorded", async () => {
    serving(false);
    const files = offered();
    shown = render(<ShareScenario scenarioId="x" />);
    await settled();

    expect(shown.container.querySelector('input[type="checkbox"]')).toBeNull();
    click(button(shown.container, "Download scenario file"));
    expect(await Promise.all(files)).toEqual([BARE]);
  });

  it("says why the file cannot be made, and offers none", async () => {
    vi.stubGlobal(
      "fetch",
      async () => new Response(JSON.stringify({ error: "gone" }), { status: 404 }),
    );
    shown = render(<ShareScenario scenarioId="x" />);
    await settled();

    expect(shown.container.querySelector('[role="alert"]')?.textContent).toBe(
      "The file cannot be made: gone",
    );
    expect(button(shown.container, "Download scenario file").disabled).toBe(true);
  });
});
