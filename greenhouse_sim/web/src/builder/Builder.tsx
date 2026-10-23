import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { greenhouseExtent, qaGreenhousePose } from "../qa/greenhouseViews";
import type { ScenarioSummary, ScenariosState } from "../scenarios";
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
import { type Assessment, Findings } from "./Findings";
import type { Installation } from "./generated/assessedTypes";
import type { BasicSetup } from "./generated/basicTypes";
import type { DraftListed } from "./generated/draftsTypes";
import { HouseForm } from "./HouseForm";
import { HouseIdentity } from "./HouseIdentity";
import { begun, edited, type History, redone, undone } from "./history";
import { RowCrops } from "./RowCrops";
import { RunStep } from "./RunStep";

/** Where the builder lives: a page of its own beside the viewer. */
export const BUILDER_PATH = "/builder";

/** A draft being edited: its edits, the format a file of it is written in,
 * and its latest revision saved, under the identifier it was saved as, if
 * it has one. Its identifier is its installation's. */
interface Editing {
  schemaVersion: number;
  history: History<Installation>;
  saved: { draftId: string; revision: number; installation: Installation } | null;
}

/** A scenario run from a draft, and where the viewer opens it. */
interface Ran {
  scenarioId: string;
  name: string;
}

const same = (a: Installation, b: Installation) => JSON.stringify(a) === JSON.stringify(b);

function ignore(): void {}

/** The revision a save of `editing` is made on: its latest saved, if it is
 * the same draft, by its identifier; none, a new draft, if it is not. */
function madeOn(editing: Editing): number | null {
  const { saved, history } = editing;
  return saved !== null && saved.draftId === history.present.installation_id
    ? saved.revision
    : null;
}

/** Whether `editing` holds what is not saved: a draft never saved, renamed
 * since, or changed since its latest revision. */
function unsaved(editing: Editing | null): boolean {
  if (editing === null) {
    return false;
  }
  return (
    madeOn(editing) === null ||
    !same(editing.saved?.installation ?? editing.history.present, editing.history.present)
  );
}

/** A fetch that `controller` cancels. */
function cancelledBy(controller: AbortController): typeof fetch {
  return (input, init) => fetch(input, { ...init, signal: controller.signal });
}

/**
 * The setup builder (P12.2): a house started from the first form, a draft
 * opened or a file imported; then its rows' crops edited many at a time,
 * each edit undone and redone in one step, what stops it running shown as
 * it changes, and the house drawn as the simulator draws it; saved as a
 * draft's next revision, exported as a file, and a saved revision run as a
 * scenario of its own, which the viewer then opens.
 *
 * Each start, save and run belongs to the draft it was asked for: an
 * answer that arrives once another draft is shown is dropped, and a save's
 * answer marks what was saved, keeping any edit made while it was on its
 * way.
 */
export function Builder() {
  const [editing, setEditing] = useState<Editing | null>(null);
  const [assessment, setAssessment] = useState<Assessment>({ status: "asked" });
  const [snapshot, setSnapshot] = useState<SceneSnapshot | null>(null);
  const [drawProblem, setDrawProblem] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<readonly DraftListed[] | null>(null);
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [ran, setRan] = useState<Ran | null>(null);
  const importer = useRef<HTMLInputElement>(null);
  // Which draft is shown: each start makes it another, so that what was
  // asked for the one before is dropped when it arrives.
  const session = useRef(0);

  const refreshDrafts = useCallback(async () => {
    const listed = await loadDrafts();
    setDrafts(listed.status === "loaded" ? listed.value : null);
    if (listed.status !== "loaded") {
      setStatus(`The drafts cannot be listed: ${listed.reason}`);
    }
  }, []);

  // The scenarios whose house can be copied, or why they cannot be listed.
  const listScenarios = useCallback(async () => {
    setScenarios({ status: "loading" });
    setScenarios(await loadScenarios());
  }, []);
  const listed = scenarios.status === "loaded" ? scenarios.scenarios : [];

  useEffect(() => {
    void refreshDrafts();
    void listScenarios();
  }, [refreshDrafts, listScenarios]);

  // What the draft shown needs, each time it changes; a request for an
  // edit since replaced is cancelled.
  const present = editing?.history.present ?? null;
  const schemaVersion = editing?.schemaVersion ?? null;
  useEffect(() => {
    if (present === null || schemaVersion === null) {
      setAssessment({ status: "asked" });
      return;
    }
    const controller = new AbortController();
    setAssessment({ status: "asked" });
    void assess(installationFile(schemaVersion, present), cancelledBy(controller)).then(
      (answer) => {
        if (!controller.signal.aborted) {
          setAssessment(
            answer.ok
              ? { status: "assessed", findings: answer.value.findings }
              : { status: "failed", problem: answer.problem },
          );
        }
      },
    );
    return () => controller.abort();
  }, [present, schemaVersion]);

  // Its house drawn, each time the house changes, not its crops.
  const house = present === null ? null : JSON.stringify([present.envelope, present.layout]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: drawn again only as the house changes
  useEffect(() => {
    if (present === null || schemaVersion === null) {
      setSnapshot(null);
      setDrawProblem(null);
      return;
    }
    const controller = new AbortController();
    void preview(installationFile(schemaVersion, present), cancelledBy(controller)).then(
      (answer) => {
        if (controller.signal.aborted) {
          return;
        }
        setSnapshot(answer.ok ? answer.value : null);
        setDrawProblem(answer.ok ? null : answer.problem);
      },
    );
    return () => controller.abort();
  }, [house, schemaVersion]);

  // Leaving the page with changes not saved asks first.
  const leaving = unsaved(editing);
  useEffect(() => {
    if (!leaving) {
      return;
    }
    function ask(event: BeforeUnloadEvent): void {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [leaving]);

  /** Another draft shown, or none: what was asked for the one before is
   * dropped when it arrives. */
  function nextSession(): number {
    session.current += 1;
    return session.current;
  }

  function begin(asked: number, next: Editing, said: string): void {
    if (session.current !== asked) {
      return;
    }
    setEditing(next);
    setRan(null);
    const id = next.history.present.installation_id;
    const kept = next.saved === null && drafts?.some((draft) => draft.draft_id === id);
    setStatus(kept ? `${said} A draft ${id} is kept already: rename this one to save it.` : said);
  }

  async function draftHouse(values: BasicSetup): Promise<void> {
    const asked = nextSession();
    setBusy(true);
    const answer = await firstDraft(values);
    setBusy(false);
    if (!answer.ok) {
      if (session.current === asked) {
        setStatus(`The house cannot be drafted: ${answer.problem}`);
      }
      return;
    }
    const { installation, schema_version } = answer.value;
    begin(
      asked,
      { schemaVersion: schema_version, history: begun(installation), saved: null },
      `Drafted ${installation.name}; not saved yet.`,
    );
  }

  async function open(draftId: string): Promise<void> {
    const asked = nextSession();
    const answer = await openDraft(draftId);
    if (answer.status !== "loaded") {
      if (session.current === asked) {
        setStatus(`The draft cannot be opened: ${answer.reason}`);
      }
      return;
    }
    const { installation, draft, schema_version } = answer.value;
    begin(
      asked,
      {
        schemaVersion: schema_version,
        history: begun(installation),
        saved: { draftId, revision: draft.revision, installation },
      },
      `Opened ${installation.name}, revision ${draft.revision}.`,
    );
  }

  async function copyHouse(scenario: ScenarioSummary, draftId: string): Promise<void> {
    const asked = nextSession();
    setBusy(true);
    const answer = await scenarioHouse(scenario.id);
    setBusy(false);
    if (answer.status !== "loaded") {
      if (session.current === asked) {
        setStatus(`${scenario.name}'s house cannot be copied: ${answer.reason}`);
      }
      return;
    }
    const { installation, schema_version } = answer.value;
    const copied = { ...installation, installation_id: draftId, name: `${scenario.name} (copy)` };
    begin(
      asked,
      { schemaVersion: schema_version, history: begun(copied), saved: null },
      `Copied ${scenario.name}'s house as ${draftId}; not saved yet.`,
    );
  }

  async function importFile(file: File): Promise<void> {
    const asked = nextSession();
    const answer = await assess(await file.text());
    if (!answer.ok) {
      if (session.current === asked) {
        setStatus(`${file.name} cannot be imported: ${answer.problem}`);
      }
      return;
    }
    const { installation, schema_version } = answer.value;
    begin(
      asked,
      { schemaVersion: schema_version, history: begun(installation), saved: null },
      `Imported ${installation.name} from ${file.name}; not saved yet.`,
    );
  }

  function startAgain(): void {
    if (unsaved(editing) && !window.confirm("Leave this draft? What is not saved is lost.")) {
      return;
    }
    nextSession();
    setEditing(null);
    setRan(null);
    setStatus("");
  }

  function edit(change: (installation: Installation) => Installation): void {
    setEditing((now) =>
      now === null ? now : { ...now, history: edited(now.history, change(now.history.present)) },
    );
    setRan(null);
  }

  function give(rows: number[], crop: Crop): void {
    if (editing === null) {
      return;
    }
    try {
      // Checked on the draft shown before it is changed.
      withCrop(editing.history.present, rows, crop);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
      return;
    }
    edit((installation) => withCrop(installation, rows, crop));
    setStatus(`Rows ${rows.join(", ")} grow ${crop.crop_model} ${crop.variety}.`);
  }

  function rename(draftId: string, name: string): void {
    edit((installation) => ({ ...installation, installation_id: draftId, name }));
    setStatus(`Called ${name} (${draftId}).`);
  }

  function step(move: typeof undone): void {
    setEditing((now) => (now === null ? now : { ...now, history: move(now.history) }));
  }

  async function save(): Promise<void> {
    if (editing === null) {
      return;
    }
    const asked = session.current;
    const sent = editing.history.present;
    setBusy(true);
    const answer = await saveDraft(
      sent.installation_id,
      installationFile(editing.schemaVersion, sent),
      madeOn(editing),
    );
    setBusy(false);
    if (session.current !== asked) {
      return;
    }
    if (!answer.ok) {
      setStatus(`It is not saved: ${answer.problem}`);
      return;
    }
    const { installation, draft } = answer.value;
    // What was saved, whatever was edited while it was on its way.
    setEditing((now) =>
      now === null
        ? now
        : { ...now, saved: { draftId: draft.draft_id, revision: draft.revision, installation } },
    );
    setStatus(`Saved as revision ${draft.revision}.`);
    await refreshDrafts();
  }

  function exportFile(): void {
    if (editing === null) {
      return;
    }
    const present = editing.history.present;
    const file = installationFile(editing.schemaVersion, present);
    const url = URL.createObjectURL(new Blob([file], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${present.installation_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function run(settings: RunSettings): Promise<void> {
    if (editing?.saved == null) {
      return;
    }
    const asked = session.current;
    setBusy(true);
    const answer = await runDraft(editing.saved.draftId, editing.saved.revision, settings);
    setBusy(false);
    if (session.current !== asked) {
      return;
    }
    if (!answer.ok) {
      setStatus(`It does not run: ${answer.problem}`);
      return;
    }
    setRan({ scenarioId: answer.value.id, name: answer.value.name });
    setStatus(`Its run is registered as ${answer.value.id}.`);
  }

  // Undo and redo from the keyboard, except where a field undoes its own
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

  const changed = unsaved(editing);
  const runWhy =
    editing?.saved == null || madeOn(editing) === null
      ? "Save it first: a run is of a revision saved."
      : changed
        ? "Save the changes first: a run is of a revision saved."
        : assessment.status !== "assessed"
          ? "It is not assessed yet."
          : assessment.findings.some((found) => found.severity === "error")
            ? "Its errors stop it running."
            : "";

  return (
    <main className="builder">
      <div className="builder-side">
        <header className="builder-bar">
          <h1>Setup builder</h1>
          {editing !== null && (
            <p data-testid="builder-draft">
              {editing.history.present.name} ({editing.history.present.installation_id}),{" "}
              {madeOn(editing) === null ? "not saved" : `revision ${editing.saved?.revision}`}
              {madeOn(editing) !== null && changed ? ", changed since" : ""}
            </p>
          )}
          {editing !== null && (
            <div className="builder-actions">
              <button type="button" onClick={startAgain}>
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
              <button type="button" disabled={!changed || busy} onClick={() => void save()}>
                Save
              </button>
              <button type="button" onClick={exportFile}>
                Export
              </button>
            </div>
          )}
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
            {scenarios.status === "unavailable" ? (
              <section className="builder-copy" aria-label="Copy a scenario's house">
                <h2>Or copy a scenario's house</h2>
                <p className="builder-note" data-testid="builder-scenarios">
                  The scenarios cannot be listed: {scenarios.reason}
                </p>
                <button type="button" disabled={busy} onClick={() => void listScenarios()}>
                  List the scenarios again
                </button>
              </section>
            ) : (
              <CopyScenario
                scenarios={listed}
                busy={busy}
                onCopy={(scenario, draftId) => void copyHouse(scenario, draftId)}
              />
            )}
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
            <HouseIdentity
              key={`${editing.history.present.installation_id}/${editing.history.present.name}`}
              draftId={editing.history.present.installation_id}
              name={editing.history.present.name}
              onRename={rename}
            />
            <Findings assessment={assessment} />
            <RowCrops installation={editing.history.present} onGive={give} />
            <RunStep
              weathers={listed[0]?.weathers ?? []}
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
          <p className="builder-note">
            {drawProblem !== null
              ? `The house cannot be drawn: ${drawProblem}`
              : "The house is drawn here once it is drafted."}
          </p>
        )}
      </div>
    </main>
  );
}
