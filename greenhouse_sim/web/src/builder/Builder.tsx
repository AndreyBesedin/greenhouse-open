import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { greenhouseExtent, qaGreenhousePose } from "../qa/greenhouseViews";
import type { ScenarioSummary } from "../scenarios";
import { loadScenarios } from "../scenarios";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { Viewport } from "../Viewport";
import {
  assess,
  firstDraft,
  installationFile,
  loadDrafts,
  openDraft,
  preview,
  type RunSettings,
  runDraft,
  saveDraft,
  scenarioHouse,
} from "./api";
import { CopyScenario } from "./CopyScenario";
import { type Crop, withCrop } from "./edits";
import { Findings } from "./Findings";
import type { Finding, Installation } from "./generated/assessedTypes";
import type { BasicSetup } from "./generated/basicTypes";
import type { DraftListed } from "./generated/draftsTypes";
import { HouseForm } from "./HouseForm";
import { begun, edited, type History, redone, undone } from "./history";
import { RowCrops } from "./RowCrops";
import { RunStep } from "./RunStep";

/** Where the builder lives: a page of its own beside the viewer. */
export const BUILDER_PATH = "/builder";

/** A draft being edited: its edits, the format a file of it is written in,
 * and its latest revision saved, if it has one. */
interface Editing {
  draftId: string;
  schemaVersion: number;
  history: History<Installation>;
  saved: { revision: number; installation: Installation } | null;
}

/** A scenario run from a draft, and where the viewer opens it. */
interface Ran {
  scenarioId: string;
  name: string;
}

const same = (a: Installation, b: Installation) => JSON.stringify(a) === JSON.stringify(b);

function ignore(): void {}

/**
 * The setup builder (P12.2): a house started from the first form, a draft
 * opened or a file imported; then its rows' crops edited many at a time,
 * each edit undone and redone in one step, what stops it running shown as
 * it changes, and the house drawn as the simulator draws it; saved as a
 * draft's next revision, exported as a file, and a saved revision run as a
 * scenario of its own, which the viewer then opens.
 */
export function Builder() {
  const [editing, setEditing] = useState<Editing | null>(null);
  const [findings, setFindings] = useState<readonly Finding[]>([]);
  const [snapshot, setSnapshot] = useState<SceneSnapshot | null>(null);
  const [drafts, setDrafts] = useState<readonly DraftListed[] | null>(null);
  const [scenarios, setScenarios] = useState<readonly ScenarioSummary[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [ran, setRan] = useState<Ran | null>(null);
  const importer = useRef<HTMLInputElement>(null);

  const refreshDrafts = useCallback(async () => {
    const listed = await loadDrafts();
    setDrafts(listed.status === "loaded" ? listed.value : null);
    if (listed.status !== "loaded") {
      setStatus(`The drafts cannot be listed: ${listed.reason}`);
    }
  }, []);

  useEffect(() => {
    void refreshDrafts();
    void loadScenarios().then((answer) => {
      if (answer.status === "loaded") {
        setScenarios(answer.scenarios);
      }
    });
  }, [refreshDrafts]);

  // What the draft shown needs, and its house, each time it changes; an
  // answer for an edit since replaced is dropped.
  const present = editing?.history.present ?? null;
  const schemaVersion = editing?.schemaVersion ?? null;
  useEffect(() => {
    if (present === null || schemaVersion === null) {
      setFindings([]);
      setSnapshot(null);
      return;
    }
    let current = true;
    const file = installationFile(schemaVersion, present);
    void assess(file).then((answer) => {
      if (current) {
        if (answer.ok) {
          setFindings(answer.value.findings);
        } else {
          setStatus(`It cannot be assessed: ${answer.problem}`);
        }
      }
    });
    void preview(file).then((answer) => {
      if (current && answer.ok) {
        setSnapshot(answer.value);
      }
    });
    return () => {
      current = false;
    };
  }, [present, schemaVersion]);

  function begin(next: Editing, said: string): void {
    setEditing(next);
    setRan(null);
    setStatus(said);
  }

  async function draftHouse(values: BasicSetup): Promise<void> {
    setBusy(true);
    const answer = await firstDraft(values);
    setBusy(false);
    if (!answer.ok) {
      setStatus(`The house cannot be drafted: ${answer.problem}`);
      return;
    }
    const { installation, schema_version } = answer.value;
    begin(
      {
        draftId: installation.installation_id,
        schemaVersion: schema_version,
        history: begun(installation),
        saved: null,
      },
      `Drafted ${installation.name}; not saved yet.`,
    );
  }

  async function open(draftId: string): Promise<void> {
    const answer = await openDraft(draftId);
    if (answer.status !== "loaded") {
      setStatus(`The draft cannot be opened: ${answer.reason}`);
      return;
    }
    const { installation, revision, schema_version } = answer.value;
    begin(
      {
        draftId,
        schemaVersion: schema_version,
        history: begun(installation),
        saved: { revision, installation },
      },
      `Opened ${installation.name}, revision ${revision}.`,
    );
  }

  async function copyHouse(scenario: ScenarioSummary, draftId: string): Promise<void> {
    setBusy(true);
    const answer = await scenarioHouse(scenario.id);
    setBusy(false);
    if (answer.status !== "loaded") {
      setStatus(`${scenario.name}'s house cannot be copied: ${answer.reason}`);
      return;
    }
    const { installation, schema_version } = answer.value;
    const copied = { ...installation, installation_id: draftId, name: `${scenario.name} (copy)` };
    begin(
      { draftId, schemaVersion: schema_version, history: begun(copied), saved: null },
      `Copied ${scenario.name}'s house as ${draftId}; not saved yet.`,
    );
  }

  async function importFile(file: File): Promise<void> {
    const answer = await assess(await file.text());
    if (!answer.ok) {
      setStatus(`${file.name} cannot be imported: ${answer.problem}`);
      return;
    }
    const { installation, schema_version } = answer.value;
    begin(
      {
        draftId: installation.installation_id,
        schemaVersion: schema_version,
        history: begun(installation),
        saved: null,
      },
      `Imported ${installation.name} from ${file.name}; not saved yet.`,
    );
  }

  function edit(next: Installation): void {
    if (editing !== null) {
      setEditing({ ...editing, history: edited(editing.history, next) });
      setRan(null);
    }
  }

  function give(rows: number[], crop: Crop): void {
    if (editing === null) {
      return;
    }
    try {
      edit(withCrop(editing.history.present, rows, crop));
      setStatus(`Rows ${rows.join(", ")} grow ${crop.crop_model} ${crop.variety}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  function step(move: typeof undone): void {
    if (editing !== null) {
      setEditing({ ...editing, history: move(editing.history) });
    }
  }

  async function save(): Promise<void> {
    if (editing === null) {
      return;
    }
    const { draftId, schemaVersion: version, history, saved } = editing;
    const answer = await saveDraft(
      draftId,
      installationFile(version, history.present),
      saved?.revision ?? null,
    );
    if (!answer.ok) {
      setStatus(`It is not saved: ${answer.problem}`);
      return;
    }
    const { revision, installation } = answer.value;
    setEditing({ ...editing, saved: { revision, installation } });
    setStatus(`Saved as revision ${revision}.`);
    await refreshDrafts();
  }

  function exportFile(): void {
    if (editing === null) {
      return;
    }
    const file = installationFile(editing.schemaVersion, editing.history.present);
    const url = URL.createObjectURL(new Blob([file], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${editing.draftId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function run(settings: RunSettings): Promise<void> {
    if (editing?.saved == null) {
      return;
    }
    setBusy(true);
    const answer = await runDraft(editing.draftId, editing.saved.revision, settings);
    setBusy(false);
    if (!answer.ok) {
      setStatus(`It does not run: ${answer.problem}`);
      return;
    }
    setRan({ scenarioId: answer.value.id, name: answer.value.name });
    setStatus(`Its run is registered as ${answer.value.id}.`);
  }

  // Undo and redo from the keyboard, except where an input undoes its own
  // typing.
  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      const typing =
        event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement;
      if (typing || !(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") {
        return;
      }
      event.preventDefault();
      setEditing((now) =>
        now === null ? now : { ...now, history: (event.shiftKey ? redone : undone)(now.history) },
      );
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // The house seen from outside, as the greenhouse's QA view frames it: once
  // for each size it has, so that an edit leaves the camera where it is.
  const extent = snapshot === null ? null : greenhouseExtent(snapshot);
  const extentKey = JSON.stringify(extent);
  // biome-ignore lint/correctness/useExhaustiveDependencies: framed once for each extent
  const pose = useMemo(
    () => (extent === null ? null : qaGreenhousePose("outside", extent)),
    [extentKey],
  );

  const changed =
    editing !== null &&
    (editing.saved === null || !same(editing.saved.installation, editing.history.present));
  const errors = findings.some((found) => found.severity === "error");
  const runWhy =
    editing?.saved == null
      ? "Save it first: a run is of a revision saved."
      : changed
        ? "Save the changes first: a run is of a revision saved."
        : errors
          ? "Its errors stop it running."
          : "";

  return (
    <main className="builder">
      <div className="builder-side">
        <header className="builder-bar">
          <h1>Setup builder</h1>
          {editing !== null && (
            <p data-testid="builder-draft">
              {editing.history.present.name} ({editing.draftId}),{" "}
              {editing.saved === null ? "not saved" : `revision ${editing.saved.revision}`}
              {editing.saved !== null && changed ? ", changed since" : ""}
            </p>
          )}
          <div className="builder-actions">
            {editing !== null && (
              <>
                <button type="button" onClick={() => setEditing(null)}>
                  Start again
                </button>
                <button
                  type="button"
                  disabled={editing.history.past.length === 0}
                  onClick={() => step(undone)}
                >
                  Undo
                </button>
                <button
                  type="button"
                  disabled={editing.history.future.length === 0}
                  onClick={() => step(redone)}
                >
                  Redo
                </button>
                <button type="button" disabled={!changed} onClick={() => void save()}>
                  Save
                </button>
                <button type="button" onClick={exportFile}>
                  Export
                </button>
              </>
            )}
          </div>
        </header>
        <p className="builder-status" role="status" data-testid="builder-status">
          {status}
          {ran !== null && (
            <>
              {" "}
              <a href={`/?scenario=${encodeURIComponent(ran.scenarioId)}`}>
                Open {ran.name} in the viewer
              </a>
            </>
          )}
        </p>
        {editing === null ? (
          <>
            <HouseForm busy={busy} onDraft={(values) => void draftHouse(values)} />
            <CopyScenario
              scenarios={scenarios}
              busy={busy}
              onCopy={(scenario, draftId) => void copyHouse(scenario, draftId)}
            />
            <section className="builder-start" aria-label="Drafts kept">
              <h2>Or open one</h2>
              {drafts === null ? (
                <p>No drafts are kept by this simulator.</p>
              ) : drafts.length === 0 ? (
                <p>No draft is saved yet.</p>
              ) : (
                <ul>
                  {drafts.map((draft) => (
                    <li key={draft.draft_id}>
                      <button type="button" onClick={() => void open(draft.draft_id)}>
                        {draft.name}
                      </button>{" "}
                      ({draft.draft_id}, revision {draft.revision})
                    </li>
                  ))}
                </ul>
              )}
              <button type="button" onClick={() => importer.current?.click()}>
                Import a file
              </button>
              <input
                ref={importer}
                type="file"
                accept="application/json,.json"
                hidden
                tabIndex={-1}
                aria-hidden="true"
                onChange={(event) => {
                  const [file] = event.target.files ?? [];
                  event.target.value = "";
                  if (file !== undefined) {
                    void importFile(file);
                  }
                }}
              />
            </section>
          </>
        ) : (
          <>
            <Findings findings={findings} />
            <RowCrops installation={editing.history.present} onGive={give} />
            <RunStep
              weathers={scenarios[0]?.weathers ?? []}
              disabled={runWhy !== "" || busy}
              why={runWhy}
              onRun={(settings) => void run(settings)}
            />
          </>
        )}
      </div>
      <div className="builder-view" data-testid="builder-view">
        {snapshot !== null ? (
          <Viewport
            snapshot={snapshot}
            presetRequest={null}
            initialPose={pose}
            onSample={ignore}
            onPointer={ignore}
            onSelect={ignore}
          />
        ) : (
          <p className="builder-note">The house is drawn here once it is drafted.</p>
        )}
      </div>
    </main>
  );
}
