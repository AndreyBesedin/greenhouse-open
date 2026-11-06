import { type ChildProcess, spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, type Page, test } from "@playwright/test";

import { unfold } from "./folds";
import { clickAt } from "./view";

// P14.7's QA scenario (`docs/roadmap/p14-models-by-manifest.md`), as it is
// recorded: the reference greenhouse's manifest names each part's model; a
// copy of it growing the simple crop is drawn with its harvest, and its
// checkpoint is refused by the organ crop's run, naming the crop; and a kind
// of equipment the viewer was built without, registered by a module of its
// own, is placed twice, run, drawn and listed. The scenario's fogger needs a
// capability that adds water to the air, which no device has, so a radiant
// panel, which heats, stands in for it, and the house's air warms where the
// fogger's would have grown more humid.

const DAY_S = 86_400;
const NOON_S = 43_200;
const HOUR_S = 3600;
// A copy's day takes the simulator the house's air and crop through each day
// before it; on CI, more.
const ARRIVES = { timeout: 240_000 };
const REFERENCE = "reference_greenhouse";
// The copy under an identifier of its own, the same on each run: a plant is
// drawn from its identifier and seed, so that another identifier grows other
// plants.
const COPY = "reference_simple_copy";
// The simple crop's first harvest round to pick a ripe fruit, on the copy's
// fourth crop work, on day 28.
const HARVESTED_DAY = 28;
// The copy's first plant, on its gutter at the start of its first row, seen
// from along the row.
const STEM = { x: 3.0, y: 2.4, z: 0.9 };
const ALONG_THE_ROW = { position: { x: 1.6, y: 2.4, z: 1.0 }, target: STEM };
const CAMERA = "1.6:2.4:1,3:2.4:0.9";

// The interpreter the browser tests serve the simulator from (`simulatorApi`),
// and the module that registers the radiant panel and serves the simulator.
const PYTHON = process.env.PYTHON ?? "python";
const RADIANT_PANEL = fileURLToPath(new URL("../../tests/radiant_panel.py", import.meta.url));
const SERVED = /greenhouse-sim API on (http:\/\/[^\s]+)\/api/;
// How much of what that simulator logs is kept, in characters.
const LOG_KEPT = 4000;

type Document = Record<string, unknown> & { models: Record<string, unknown> };

/** A scenario's file as the simulator at `api` serves it, the browser
 * tests' own unless given, as `change` makes it. */
async function changedFile(
  page: Page,
  scenario: string,
  change: (document: Document) => void,
  api = "",
): Promise<string> {
  const response = await page.request.get(`${api}/api/scenarios/${scenario}/file`);
  expect(response.ok()).toBe(true);
  const document = JSON.parse(((await response.json()) as { text: string }).text) as Document;
  change(document);
  return JSON.stringify(document);
}

async function upload(page: Page, file: string, api = ""): Promise<void> {
  const uploaded = await page.request.post(`${api}/api/scenarios/upload`, {
    headers: { "Content-Type": "application/json" },
    data: file,
  });
  expect(uploaded.ok(), await uploaded.text()).toBe(true);
}

test("P14.7's QA: the reference greenhouse's manifest names each part's model and version", async ({
  page,
}) => {
  await page.goto(`/?scenario=${REFERENCE}&qa=1`);
  await unfold(page, "Display");
  await expect(
    page.getByRole("region", { name: "QA mode" }).getByTestId("manifest-models"),
  ).toHaveText(
    "weather: seasonal v1, air field: uniform v1, crop: organ v1, crop walk: walk v1, " +
      "sunlight: haurwitz_erbs v1, sensors: sampled v1, house air: grid v1, controller: loops v1",
    ARRIVES,
  );
});

test("P14.7's QA: a copy growing the simple crop is drawn with its harvest, and the organ crop's run refuses its checkpoint", async ({
  page,
}) => {
  test.setTimeout(600_000);
  await upload(
    page,
    await changedFile(page, REFERENCE, (document) => {
      document.greenhouse_id = COPY;
      // Named so that it does not start "Reference greenhouse": it stays
      // registered in the lane's simulator, where later specs, such as the
      // README demo's, search for the reference greenhouse by that prefix.
      document.name = "Simple-crop copy of the reference greenhouse";
      document.description = "The reference greenhouse, its rows growing the simple crop.";
      document.models.crop = { model: "simple", parameters: {} };
      const { row_crops } = document.installation as { row_crops: { crop_model: string }[] };
      for (const row of row_crops) {
        row.crop_model = "simple";
      }
    }),
  );

  await test.step("its manifest names the simple crop", async () => {
    await page.goto(`/?scenario=${COPY}&qa=1`);
    await unfold(page, "Display");
    await expect(
      page.getByRole("region", { name: "QA mode" }).getByTestId("manifest-models"),
    ).toContainText("crop: simple v2", ARRIVES);
  });

  await test.step("its plants are drawn, and a plant's harvest is shown", async () => {
    await page.goto(
      `/?scenario=${COPY}&field=climate&t=${HARVESTED_DAY * DAY_S + NOON_S}&camera=${CAMERA}`,
    );
    await expect(page.getByTestId("scene-status")).toContainText(
      `${COPY}, day ${HARVESTED_DAY},`,
      ARRIVES,
    );
    const selected = page.getByTestId("selected-entity");
    await expect(async () => {
      await clickAt(page, STEM, ALONG_THE_ROW);
      await expect(selected).toHaveText(`${COPY}_plant_001`, { timeout: 500 });
    }).toPass(ARRIVES);
    await expect(page.getByTestId("property-age_days")).toHaveText(String(HARVESTED_DAY));
    const harvest = Number(await page.getByTestId("property-cumulative_harvest_g").textContent());
    expect(harvest).toBeGreaterThan(0);
  });

  await test.step("its checkpoint, into the organ crop's run, is refused naming the crop", async () => {
    const panel = page.locator("details.checkpoints");
    const kept = panel.getByTestId("checkpoint");
    await page.goto(`/?scenario=${COPY}&field=climate&t=${DAY_S + HOUR_S}`);
    await expect(page.getByTestId("climate-time")).toHaveText("day 1, 1 h 00 min", ARRIVES);
    await panel.locator("summary").click();
    await panel.getByRole("button", { name: "Save day 1's start" }).click();
    const saved = kept.filter({ hasText: "day 1:" });
    await expect(saved).toHaveCount(1, ARRIVES);
    const href = await saved.getByRole("link", { name: "Download" }).getAttribute("href");
    const checkpoint = (await (await page.request.get(href ?? "")).json()) as Document;
    expect(checkpoint.models.crop).toMatchObject({ model: "simple", version: 2 });
    // A checkpoint names its scenario and the version of its manifest, and
    // is taken into that scenario's run: one for the organ crop's run names
    // the reference greenhouse's.
    const { version } = (await (
      await page.request.get(`/api/scenarios/${REFERENCE}/manifest`)
    ).json()) as { version: string };

    await page.goto(`/?scenario=${REFERENCE}&field=climate&t=${HOUR_S}`);
    await expect(page.getByTestId("climate-time")).toHaveText("1 h 00 min", ARRIVES);
    await panel.locator("summary").click();
    await panel.locator("input[type=file]").setInputFiles({
      name: "checkpoint.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify({ ...checkpoint, scenario_id: REFERENCE, manifest: version }),
      ),
    });
    await expect(panel.getByTestId("checkpoints-problem")).toHaveText(
      "a checkpoint made with the simple model of the crop, version 2: its run's is the " +
        "organ model, version 1",
      ARRIVES,
    );
  });
});

test.describe("a kind of equipment the viewer was built without", () => {
  // A simulator of its own, with the radiant panel registered: the one the
  // other browser tests share knows no such kind, and has no way to be told
  // of one (decision 0054: no entry points yet).
  let simulator: ChildProcess | undefined;
  let api = "";

  test.beforeAll(async () => {
    const state = mkdtempSync(join(tmpdir(), "greenhouse-sim-radiant-panel-"));
    const started = spawn(
      PYTHON,
      [RADIANT_PANEL, "--port", "0", "--drafts", join(state, "drafts.sqlite3")],
      { env: { ...process.env, XDG_STATE_HOME: state }, stdio: ["ignore", "pipe", "pipe"] },
    );
    simulator = started;
    // What it logs, its requests among them, is kept for the error of a
    // simulator that does not start.
    let logged = "";
    started.stderr?.on("data", (chunk: Buffer) => {
      logged = (logged + chunk.toString()).slice(-LOG_KEPT);
    });
    api = await new Promise<string>((resolve, reject) => {
      let said = "";
      started.stdout?.on("data", (chunk: Buffer) => {
        said += chunk.toString();
        const served = SERVED.exec(said);
        if (served?.[1] !== undefined) {
          resolve(served[1]);
        }
      });
      started.on("exit", (code) =>
        reject(new Error(`the simulator ended with ${code} before it served:\n${logged}`)),
      );
    });
  });

  test.afterAll(() => {
    simulator?.kill();
  });

  test("P14.7's QA: two radiant panels, registered by a module of their own, placed, run, drawn and listed", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    // The viewer, as it is built, asks this simulator; what the test asks
    // itself, it asks of it by its address.
    await page.route("**/api/**", async (route) => {
      const asked = new URL(route.request().url());
      const response = await route.fetch({ url: `${api}${asked.pathname}${asked.search}` });
      await route.fulfill({ response });
    });
    const id = "radiant_box";
    await upload(
      page,
      await changedFile(
        page,
        "climate_box",
        (document) => {
          document.greenhouse_id = id;
          document.name = "Radiant box";
          document.description = "The climate box with two radiant panels.";
          const { layout } = document.installation as { layout: { equipment: object[] } };
          for (const [number, x] of [
            [1, 3.0],
            [2, 8.0],
          ]) {
            layout.equipment.push({
              actuator_id: `panel_${number}`,
              kind: "radiant_panel",
              base: { x, y: 1.0, z: 0.0 },
              size_x: 0.2,
              size_y: 1.0,
              size_z: 0.8,
              power_w: 5000.0,
            });
          }
        },
        api,
      ),
      api,
    );

    await page.goto(`/?scenario=${id}&field=climate&t=${HOUR_S}`);
    await expect(page.getByTestId("climate-time")).toHaveText("1 h 00 min", ARRIVES);
    await unfold(page, "Equipment");
    await unfold(page, "House air");
    const equipment = page.getByRole("group", { name: "Equipment" });
    const air = page.getByTestId("house-air");

    await test.step("drawn and listed by what they do, and off", async () => {
      const scene = (await (await page.request.get(`${api}/api/scenarios/${id}/scene`)).json()) as {
        entities: { entity_id: string; properties: Record<string, unknown> }[];
      };
      const panels = scene.entities.filter(
        (entity) => entity.properties.device_kind === "radiant_panel",
      );
      expect(panels.map((entity) => entity.entity_id)).toEqual([`${id}_panel_1`, `${id}_panel_2`]);
      for (const name of ["panel 1", "panel 2"]) {
        await expect(equipment.getByRole("checkbox", { name })).not.toBeChecked();
      }
      await expect(air).toContainText("Air 8.0 °C, all off 8.0 °C");
    });

    await test.step("switched on, an hour on: the house's air warms", async () => {
      for (const name of ["panel 1", "panel 2"]) {
        await equipment.getByRole("checkbox", { name }).check();
      }
      await expect(page).toHaveURL(/&schedule=3600:panel_1:1,3600:panel_2:1(&|$)/);
      await page.getByRole("slider", { name: "Time of day" }).fill(String(2 * HOUR_S));
      await expect(page.getByTestId("climate-time")).toHaveText("2 h 00 min", ARRIVES);
      await expect(page.getByTestId("equipment-summary")).toHaveText(
        /^Equipment: panel 1 100%, panel 2 100%;/,
      );
      // The panel keeps the hour before's trace while the next one loads,
      // so the reading is asked again until the warmed air arrives.
      await expect
        .poll(
          async () => Number(/Air ([\d.]+) °C/.exec((await air.textContent()) ?? "")?.[1]),
          ARRIVES,
        )
        .toBeGreaterThan(8.0 + 5);
      await expect(air).toContainText(/all off 8\.0 °C/);
    });
    // The view may still be asking for what it draws.
    await page.unrouteAll({ behavior: "ignoreErrors" });
  });
});
