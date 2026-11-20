import { readFileSync } from "node:fs";

import { expect, type Locator, test } from "@playwright/test";

import { REPLAY_PATH, replayTarget } from "../src/landing/paths";
import { lowContrast } from "./contrast.ts";

// A crop parameter set edited in the setup builder, beside the rows (P20.5): a
// new version drawn from the schema of its model's parameters, each with its
// unit, range and source, a fixed one read only; a value outside its range
// refused by its field; then saved as a version, compared with its base and
// downloaded as its file. Then a run under it, chosen in the new-run form of the
// scenario the house runs as: a run of the scenario the simulator registers for
// the house under that set, whose manifest answer names it by its name, version
// and digest. The simulator served keeps the sets in a run store of the test
// run's own.

// On CI the simulator may still be working out what the spec before this one
// asked for.
const ARRIVES = { timeout: 60_000 };
// A worker is a process started from nothing, which then computes its day.
const WORKS = { timeout: 90_000 };
// A compact control's least height and width (`--target-compact`, P19.9).
const COMPACT_TARGET_PX = 24;
const CONTROLS = "button, select, input";

/** Each of `controls` smaller than a compact target, by its name. */
async function tooSmall(controls: Locator): Promise<string[]> {
  const small: string[] = [];
  for (const control of await controls.all()) {
    const box = await control.boundingBox();
    if ((box?.height ?? 0) < COMPACT_TARGET_PX || (box?.width ?? 0) < COMPACT_TARGET_PX) {
      small.push(
        `${await control.evaluate((element) => element.id)}: ${box?.width} by ${box?.height}`,
      );
    }
  }
  return small;
}

test("builder: a crop parameter set edited, refused outside its range, saved, compared, downloaded and run", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // A name of its own, so that a retry against the same simulator saves its
  // own first version.
  const stamp = Date.now();
  const name = `e2e_brighter_${stamp}`;
  const draft = `e2e_sets_${stamp}`;

  await page.goto("/builder");
  const house = page.getByRole("form", { name: "A new house", exact: true });
  await house.getByLabel("Identifier", { exact: true }).fill(draft);
  await house.getByLabel("Crop model", { exact: true }).selectOption("reduced_tomgro");
  await house.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-status")).toContainText("Drafted", ARRIVES);

  // The rows grow Reduced-State TOMGRO: its published set is chosen first.
  const sets = page.getByRole("region", { name: "Crop parameters", exact: true });
  await expect(sets.getByLabel("Parameter set", { exact: true })).toHaveValue("gnvman v1", ARRIVES);
  await expect(sets.getByTestId("parameter-set-chosen")).toContainText(
    "Its model's published set, made for reduced_tomgro version 1. Its digest is sha256:",
  );
  await expect(sets.getByRole("button", { name: "Compare with its base" })).toBeDisabled();

  // A new version, folded until opened, each parameter as the model's schema
  // describes it: what it is, its unit and range, and its source.
  await sets.getByText("A new version, based on gnvman v1", { exact: true }).click();
  const form = sets.getByRole("form");
  const alphaLabel = /^alpha_F: the share of the day's net growth/;
  const alpha = form.getByLabel(alphaLabel);
  await expect(alpha).toHaveValue("0.8");
  await expect(alpha).toHaveAccessibleDescription("In fraction d⁻¹, from 0 to 1.");
  const alphaBlock = form
    .locator(".builder-parameter")
    .filter({ has: page.getByLabel(alphaLabel) });
  await alphaBlock.getByText("Where it comes from", { exact: true }).click();
  await expect(alphaBlock).toContainText("Oliveira et al. v0.4.0");
  await expect(alphaBlock).toContainText("Its most, 1: a share, of all of it at most");
  // A fixed parameter is read only, and says why.
  const conversion = form.getByLabel(/^D, an input: the conversion/);
  await expect(conversion).not.toBeEditable();
  await expect(conversion).toHaveAccessibleDescription(
    "In g CH₂O s d⁻¹ µmol⁻¹ CO₂. Fixed: a conversion of units: no set changes it.",
  );
  // Its controls are targets, its words stand out from what they are drawn on.
  expect(await tooSmall(sets.locator(CONTROLS))).toEqual([]);
  expect(await lowContrast(sets)).toEqual([]);

  // Outside its range: the simulator refuses it, by its field, and keeps nothing.
  await form.getByLabel("Name", { exact: true }).fill(name);
  await alpha.fill("2");
  await form.getByLabel("Why alpha_f", { exact: true }).fill("a browser test's");
  await form.getByRole("button", { name: "Save this version" }).click();
  await expect(sets.getByTestId("parameter-set-problem")).toHaveText(
    "Not saved: parameters.alpha_f: Input should be less than or equal to 1",
    ARRIVES,
  );
  await expect(alpha).toHaveAttribute("aria-invalid", "true");
  await expect(alpha).toHaveAccessibleDescription(
    "In fraction d⁻¹, from 0 to 1. Input should be less than or equal to 1",
  );
  await expect(sets.getByLabel("Parameter set", { exact: true }).locator("option")).toHaveText([
    "gnvman v1, published",
  ]);
  // Within it: saved as its name's first version, which is then chosen.
  await alpha.fill("0.7");
  await form.getByRole("button", { name: "Save this version" }).click();
  const saved = new RegExp(`^Saved as ${name} v1, (sha256:[0-9a-f]{64})\\.$`);
  await expect(sets.getByTestId("parameter-set-status")).toHaveText(saved, ARRIVES);
  const digest = saved.exec(await sets.getByTestId("parameter-set-status").innerText())?.[1];
  await expect(sets.getByTestId("parameter-set-problem")).toHaveCount(0);
  await expect(sets.getByLabel("Parameter set", { exact: true })).toHaveValue(`${name} v1`);
  await expect(sets.getByTestId("parameter-set-chosen")).toContainText("Based on gnvman v1");

  // Compared with its base: the one value it changes.
  await sets.getByRole("button", { name: "Compare with its base" }).click();
  const comparison = sets.getByRole("table");
  await expect(comparison).toContainText(
    `${name} v1 against its base, gnvman v1: 1 parameter differs`,
    ARRIVES,
  );
  await expect(comparison.getByRole("rowheader")).toHaveText(["alpha_f"]);
  await expect(comparison.locator("tbody td")).toHaveText(["0.8", "0.7"]);
  // Downloaded, as the simulator writes its file.
  const downloading = page.waitForEvent("download");
  await sets.getByRole("button", { name: "Download its file" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(`reduced_tomgro.${name}.v1.parameter_set.json`);
  expect(JSON.parse(readFileSync(await download.path(), "utf8"))).toMatchObject({
    model: "reduced_tomgro",
    name,
    version: 1,
    based_on: { name: "gnvman", version: 1 },
    parameters: { alpha_f: 0.7 },
    why: { alpha_f: "a browser test's" },
  });

  // Run under it: the house, saved, runs as a scenario of its own, a day long,
  // whose new-run form offers its crop model's sets, its own, the published, first.
  const scenarioId = `${draft}_r1`;
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByTestId("builder-status")).toHaveText("Saved as revision 1.", ARRIVES);
  await page.getByRole("form", { name: "Run it" }).getByLabel("Days").fill("1");
  await page.getByRole("button", { name: "Run this revision" }).click();
  await expect(page.getByTestId("builder-status")).toContainText(
    `Its run is registered as ${scenarioId}.`,
    ARRIVES,
  );
  await page.getByRole("link", { name: "Start a run of it" }).click();
  const dialog = page.getByRole("dialog");
  const chosen = dialog.getByLabel("Parameter set", { exact: true });
  await expect(chosen).toHaveValue("gnvman v1", ARRIVES);
  await expect(chosen.locator("option", { hasText: `${name} v1` })).toHaveCount(1, ARRIVES);
  expect(await lowContrast(dialog.locator("form"))).toEqual([]);
  await chosen.selectOption(`${name} v1`);
  await dialog.getByLabel("Seconds to compute a day").fill("");
  await dialog.getByRole("button", { name: "Start run" }).click();
  await expect(page).toHaveURL(new RegExp(`${REPLAY_PATH}\\?run=.*&follow=1$`), ARRIVES);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`under ${name} v1`, ARRIVES);
  // A worker runs it from the store, its scenario's file carrying the set.
  await expect(page.getByRole("status", { name: "Run status" })).toHaveText(/Finished/, WORKS);

  // The run is one of the scenario registered for the house under the set, and
  // reports the set by its name, version and digest, as saved.
  const target = replayTarget(new URL(page.url()).search);
  expect(target).not.toBeNull();
  const epoch = await page.request.get(`/api/runs/${target?.runId}/epochs/${target?.epoch}`);
  const run = await epoch.json();
  expect(run.scenario_id).toBe(`${scenarioId}_${name}_v1`);
  const manifest = await page.request.get(`/api/scenarios/${run.scenario_id}/manifest`);
  expect((await manifest.json()).parameter_set).toEqual({
    name,
    version: 1,
    digest,
    made_for: 1,
  });
});

test("start page: a packaged scenario's new run says why it takes its published set alone", async ({
  page,
}) => {
  await page.goto("/#run=tomgro_house");
  const dialog = page.getByRole("dialog");

  await expect(dialog.getByTestId("run-parameter-set")).toHaveText(
    "Its crop's parameter set: gnvman v1. A packaged scenario runs its crop model's published " +
      "set alone. Its house runs under another as a new scenario made from it in the builder.",
    ARRIVES,
  );
  await expect(dialog.getByLabel("Parameter set", { exact: true })).toHaveCount(0);
});
