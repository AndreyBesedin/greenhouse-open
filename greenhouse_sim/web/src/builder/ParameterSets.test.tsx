// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  button,
  choose,
  click,
  enter,
  type Rendered,
  render,
  said,
  select,
} from "../testing/render";
import { ParameterSets } from "./ParameterSets";
import type { SetListed, SetRead } from "./parameterSetLibrary";

const SETS = "/api/parameter-sets/reduced_tomgro";
const DIGEST = `sha256:${"a".repeat(64)}`;
const SAVED_DIGEST = `sha256:${"b".repeat(64)}`;
const TYPES_OWN = "none in its source: the field's type's";

/** Two of Reduced-State TOMGRO's parameters, as its schema describes them. */
const SCHEMA = {
  properties: {
    alpha_f: {
      description: "alpha_F: the share of the day's net growth to the fruit, at most",
      unit: "fraction d⁻¹",
      source: "Oliveira et al. v0.4.0",
      minimum: 0,
      maximum: 1,
      range_from: { least: TYPES_OWN, most: "a share, of all of it at most" },
      type: "number",
    },
    d: {
      description: "D, an input: a conversion",
      unit: "g CH₂O s d⁻¹ µmol⁻¹ CO₂",
      source: "Jones et al. 1999",
      exclusiveMinimum: 0,
      readOnly: true,
      fixed: "a conversion of units: no set changes it",
      range_from: { least: TYPES_OWN, most: TYPES_OWN },
      type: "number",
    },
  },
};

const PUBLISHED: SetListed = {
  model: "reduced_tomgro",
  name: "gnvman",
  version: 1,
  digest: DIGEST,
  based_on: null,
  made_for: 1,
  cultivar: null,
  description: "",
  published: true,
};
const SAVED: SetListed = {
  ...PUBLISHED,
  name: "brighter",
  digest: SAVED_DIGEST,
  based_on: { name: "gnvman", version: 1, digest: DIGEST },
  published: false,
};

function read(set: SetListed, values: Record<string, number>): SetRead {
  return { ...set, parameters: values, why: {}, values };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

/** The simulator's refusal of αF, by its field. */
function refusedAlpha(message: string): Response {
  return json(
    {
      error: `parameters.alpha_f: ${message}`,
      problems: [{ field: "parameters.alpha_f", message }],
    },
    400,
  );
}

/** The simulator, stood in for: Reduced-State TOMGRO's published set, and the
 * one a save keeps, or that it keeps already; refusing an αF that is no
 * number, or above 1, as its range does. */
function serving({ kept = false } = {}): { saves: unknown[] } {
  const saves: unknown[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "POST") {
      const file = JSON.parse(String(init.body));
      const alpha: unknown = file.parameters.alpha_f;
      if (alpha !== undefined && typeof alpha !== "number") {
        return refusedAlpha("Input should be a valid number");
      }
      if (typeof alpha === "number" && alpha > 1) {
        return refusedAlpha("Input should be less than or equal to 1");
      }
      saves.push(file);
      return json(SAVED);
    }
    const answers: Record<string, unknown> = {
      [SETS]: saves.length === 0 && !kept ? [PUBLISHED] : [PUBLISHED, SAVED],
      [`${SETS}/schema`]: SCHEMA,
      [`${SETS}/gnvman/1`]: read(PUBLISHED, { alpha_f: 0.8, d: 2.59 }),
      [`${SETS}/brighter/1`]: read(SAVED, { alpha_f: 0.7, d: 2.59 }),
      [`${SETS}/gnvman/1/compare/brighter/1`]: {
        first: { name: "gnvman", version: 1, digest: DIGEST },
        second: { name: "brighter", version: 1, digest: SAVED_DIGEST },
        changes: [{ name: "alpha_f", first: 0.8, second: 0.7 }],
      },
      [`${SETS}/brighter/1/file`]: {
        file_name: "reduced_tomgro.brighter.v1.parameter_set.json",
        text: '{"name": "brighter"}\n',
      },
    };
    return url in answers
      ? json(answers[url])
      : json({ error: "'simple' has no parameter sets: those that have are reduced_tomgro" }, 404);
  });
  return { saves };
}

async function settled(): Promise<void> {
  await act(async () => {
    for (let turn = 0; turn < 20; turn += 1) {
      await Promise.resolve();
    }
  });
}

function control(within: ParentNode, name: string): HTMLInputElement {
  const found = within.querySelector<HTMLInputElement>(`input[name="${name}"]`);
  if (found === null) {
    throw new Error(`no input named ${name}`);
  }
  return found;
}

/** The field whose label is `label`, by the label beside it. */
function labelled(within: ParentNode, label: string): HTMLInputElement {
  const found = [...within.querySelectorAll("label")].find((each) => each.textContent === label);
  const input = found === undefined ? null : document.getElementById(found.htmlFor);
  if (!(input instanceof HTMLInputElement)) {
    throw new Error(`no field labelled ${label}`);
  }
  return input;
}

/** What describes a field: its hint and its problem. */
function described(input: HTMLInputElement): string {
  return (input.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" | ");
}

describe("a crop model's parameter sets, edited beside the rows (P20.5)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("starts from the published set, each parameter with its unit, range and source", async () => {
    serving();
    shown = render(<ParameterSets model="reduced_tomgro" />);
    await settled();

    expect(select(shown.container, "Parameter set").value).toBe("gnvman v1");
    expect(said(shown.container, "parameter-set-chosen")).toBe(
      `Its model's published set, made for reduced_tomgro version 1. Its digest is ${DIGEST}.`,
    );
    const alpha = control(shown.container, "alpha_f");
    expect(alpha.value).toBe("0.8");
    expect(alpha.readOnly).toBe(false);
    expect(described(alpha)).toBe("In fraction d⁻¹, from 0 to 1.");
    // Held as typed, for the simulator to check, and entered as a decimal.
    expect([alpha.type, alpha.inputMode]).toEqual(["text", "decimal"]);
    expect(shown.container.textContent).toContain("Oliveira et al. v0.4.0");
    expect(shown.container.textContent).toContain("Its most, 1: a share, of all of it at most");
    // A fixed parameter is read only, and says why.
    const d = control(shown.container, "d");
    expect(d.readOnly).toBe(true);
    expect(described(d)).toBe(
      "In g CH₂O s d⁻¹ µmol⁻¹ CO₂. Fixed: a conversion of units: no set changes it.",
    );
    // The published set is based on none.
    expect(button(shown.container, "Compare with its base").disabled).toBe(true);
  });

  it("shows a value outside its range refused by its field, then saves, compares and downloads", async () => {
    const { saves } = serving();
    const files: Promise<string>[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((file) => {
      files.push((file as Blob).text());
      return "blob:offered";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    shown = render(<ParameterSets model="reduced_tomgro" />);
    await settled();

    enter(labelled(shown.container, "Name"), "brighter");
    enter(control(shown.container, "alpha_f"), "2");
    // A value changed asks where it comes from.
    enter(labelled(shown.container, "Why alpha_f"), "a calibration");
    click(button(shown.container, "Save this version"));
    await settled();

    expect(saves).toEqual([]);
    expect(described(control(shown.container, "alpha_f"))).toBe(
      "In fraction d⁻¹, from 0 to 1. | Input should be less than or equal to 1",
    );
    expect(said(shown.container, "parameter-set-problem")).toBe(
      "Not saved: parameters.alpha_f: Input should be less than or equal to 1",
    );

    enter(control(shown.container, "alpha_f"), "0.7");
    expect(described(control(shown.container, "alpha_f"))).toBe("In fraction d⁻¹, from 0 to 1.");
    click(button(shown.container, "Save this version"));
    await settled();

    expect(saves).toEqual([
      {
        model: "reduced_tomgro",
        name: "brighter",
        based_on: { name: "gnvman", version: 1, digest: DIGEST },
        parameters: { alpha_f: 0.7 },
        why: { alpha_f: "a calibration" },
        made_for: 1,
        cultivar: null,
        description: "",
      },
    ]);
    expect(said(shown.container, "parameter-set-status")).toBe(
      `Saved as brighter v1, ${SAVED_DIGEST}.`,
    );
    expect(said(shown.container, "parameter-set-problem")).toBeNull();
    // The version saved is the one chosen now, and a version of it starts
    // from its values, none changed.
    expect(select(shown.container, "Parameter set").value).toBe("brighter v1");
    expect(said(shown.container, "parameter-set-chosen")).toContain("Based on gnvman v1");
    expect(control(shown.container, "alpha_f").value).toBe("0.7");
    expect(shown.container.textContent).not.toContain("Why alpha_f");

    click(button(shown.container, "Compare with its base"));
    await settled();
    const rows = [...shown.container.querySelectorAll(".builder-comparison tbody tr")];
    expect(rows.map((row) => row.textContent)).toEqual(["alpha_f0.80.7"]);
    expect(shown.container.querySelector("caption")?.textContent).toBe(
      "brighter v1 against its base, gnvman v1: 1 parameter differs",
    );

    click(button(shown.container, "Download its file"));
    await settled();
    expect(await Promise.all(files)).toEqual(['{"name": "brighter"}\n']);
  });

  it("sends an entry that reads as no number, for the simulator to refuse, not as unchanged", async () => {
    const { saves } = serving();
    shown = render(<ParameterSets model="reduced_tomgro" />);
    await settled();

    enter(labelled(shown.container, "Name"), "brighter");
    enter(control(shown.container, "alpha_f"), "1e");
    expect(control(shown.container, "alpha_f").value).toBe("1e");
    enter(labelled(shown.container, "Why alpha_f"), "a typo");
    click(button(shown.container, "Save this version"));
    await settled();

    expect(saves).toEqual([]);
    expect(described(control(shown.container, "alpha_f"))).toBe(
      "In fraction d⁻¹, from 0 to 1. | Input should be a valid number",
    );
  });

  it("acts on the set chosen only once it is read, and keeps nothing typed meanwhile", async () => {
    serving({ kept: true });
    shown = render(<ParameterSets model="reduced_tomgro" />);
    await settled();
    const saveButton = () => button(shown?.container ?? document, "Save this version");
    expect(button(shown.container, "Download its file").disabled).toBe(false);

    choose(select(shown.container, "Parameter set"), "brighter v1");

    // Asked for, not yet read: what is shown is still gnvman's.
    expect(control(shown.container, "alpha_f").value).toBe("0.8");
    expect(control(shown.container, "alpha_f").disabled).toBe(true);
    expect(button(shown.container, "Download its file").disabled).toBe(true);
    expect(button(shown.container, "Compare with its base").disabled).toBe(true);
    expect(saveButton().disabled).toBe(true);
    await settled();

    expect(control(shown.container, "alpha_f").value).toBe("0.7");
    expect(control(shown.container, "alpha_f").disabled).toBe(false);
    expect(button(shown.container, "Compare with its base").disabled).toBe(false);
    expect(saveButton().disabled).toBe(false);
  });

  it("says why the rows' model has no sets, and that rows of none have no model", async () => {
    serving();
    shown = render(<ParameterSets model="simple" />);
    await settled();

    expect(said(shown.container, "parameter-sets-unavailable")).toBe(
      "The rows grow simple: 'simple' has no parameter sets: those that have are reduced_tomgro.",
    );
    shown.unmount();
    shown = render(<ParameterSets model={null} />);
    expect(shown.container.textContent).toContain("The rows grow no crop yet.");
  });
});
