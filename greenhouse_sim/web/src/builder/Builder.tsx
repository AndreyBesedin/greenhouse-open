import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { entityBounds, type OverlayPrimitive } from "../debug/overlays";
import { HomeButton } from "../landing/HomeButton";
import {
  BUILDER_PATH,
  draftAsked,
  LANDING_PATH,
  newRunAddress,
  replayAddress,
} from "../landing/paths";
import { missingWeatherProblem, uploadFile } from "../landing/sendScenarioFile";
import { DEFAULT_PACE_S, startRun } from "../landing/startRun";
import {
  keepSettings,
  keptFields,
  keptHouse,
  uploadedHouse,
  uploadedScenario,
} from "../landing/uploaded";
import { greenhouseExtent, qaGreenhousePose } from "../qa/greenhouseViews";
import type { ScenarioSummary, ScenariosState } from "../scenarios";
import { loadScenarios } from "../scenarios";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { Viewport } from "../Viewport";
import {
  assess,
  edit as editItems,
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
import { FinishStep } from "./FinishStep";
import type { Assessed, Installation } from "./generated/assessedTypes";
import type { BasicSetup } from "./generated/basicTypes";
import type { DraftListed } from "./generated/draftsTypes";
import type { Edit } from "./generated/editTypes";
import { HouseForm } from "./HouseForm";
import { HouseIdentity } from "./HouseIdentity";
import { begun, edited, type History, redone, undone } from "./history";
import { Inspector } from "./Inspector";
import { Items } from "./Items";
import { drawnAs } from "./palette";
import { RowCrops } from "./RowCrops";
import { FIRST_RUN, type RunFields, RunStep, settingsOf } from "./RunStep";
import { ShareScenario } from "./ShareScenario";
import { offerFile } from "./scenarioFile";

/** What an installation's file is called when it is downloaded, as a scenario's
 * is `.scenario.json`. */
const HOUSE_FILE_SUFFIX = ".house.json";

/** What outlines an item an error names, on the house. */
const FINDING_COLOR = "#e5484d";

export { BUILDER_PATH };

/** A draft being edited: its edits, the format a file of it is written in,
 * and its latest revision saved, under the identifier it was saved as, if
 * it has one. Its identifier is its installation's. */
interface Editing {
  /** The scenario whose file this draft was opened from, if it was. */
  from?: string;
  schemaVersion: number;
  history: History<Installation>;
  saved: { draftId: string; revision: number; installation: Installation } | null;
}

/** A draft saved: its identifier, its revision and the house that revision
 * holds. */
interface Kept {
  draftId: string;
  revision: number;
  house: Installation;
}

/** A scenario run from a draft, and where the viewer opens it. */
interface Ran {
  scenarioId: string;
  name: string;
}

const same = (a: Installation, b: Installation) => JSON.stringify(a) === JSON.stringify(b);

function ignore(): void {}

/** Goes to an address, a page of its own. */
function goTo(address: string): void {
  location.assign(address);
}

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
export function Builder({
  navigate = goTo,
  hash = location.hash,
}: {
  navigate?: (address: string) => void;
  /** The address's fragment, which can ask for an uploaded scenario. */
  hash?: string;
}) {
  const [editing, setEditing] = useState<Editing | null>(null);
  const [assessment, setAssessment] = useState<Assessment>({ status: "asked" });
  const [snapshot, setSnapshot] = useState<SceneSnapshot | null>(null);
  const [drawProblem, setDrawProblem] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<readonly DraftListed[] | null>(null);
  const [scenarios, setScenarios] = useState<ScenariosState>({ status: "loading" });
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [ran, setRan] = useState<Ran | null>(null);
  // What the run step holds, kept while the draft is shown.
  const [runFields, setRunFields] = useState<RunFields>(FIRST_RUN);
  // The items chosen, in the list or the view, by their identifiers.
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const importer = useRef<HTMLInputElement>(null);
  // Which draft is shown: each start makes it another, so that what was
  // asked for the one before is dropped when it arrives.
  const session = useRef(0);
  // How many edits the simulator is making of the draft shown: until each
  // is made, the draft exported would leave it out.
  const editsUnderWay = useRef(0);
  // The draft as last drawn, for an answer to check it was asked for this
  // one as it stands.
  const shown = useRef<Editing | null>(null);
  shown.current = editing;

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

  // An uploaded scenario or a draft the address names is opened once, as the
  // start page sends it here.
  // biome-ignore lint/correctness/useExhaustiveDependencies: opened for the address the page was loaded at
  useEffect(() => {
    const uploaded = uploadedScenario(hash);
    const house = uploadedHouse(hash);
    const draft = draftAsked(hash);
    if (uploaded !== null) {
      void openUploaded(uploaded);
    } else if (house !== null) {
      void openUploadedHouse(house);
    } else if (draft !== null) {
      void open(draft);
    }
  }, []);

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

  function begin(
    asked: number,
    next: Editing,
    said: string,
    known: readonly DraftListed[] | null = drafts,
  ): void {
    if (session.current !== asked) {
      return;
    }
    setEditing(next);
    setChosen(new Set());
    setRan(null);
    const id = next.history.present.installation_id;
    const kept = next.saved === null && known?.some((draft) => draft.draft_id === id);
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

  /** An uploaded scenario's house, as the simulator registered it, opened as
   * a draft not saved, with the run settings its file held. */
  async function openUploaded(scenarioId: string): Promise<void> {
    const asked = nextSession();
    setBusy(true);
    const answer = await scenarioHouse(scenarioId);
    setBusy(false);
    if (answer.status !== "loaded") {
      if (session.current === asked) {
        setStatus(`The uploaded scenario cannot be opened: ${answer.reason}`);
      }
      return;
    }
    // Another draft opened meanwhile keeps its own run settings.
    if (session.current !== asked) {
      return;
    }
    const { installation, schema_version } = answer.value;
    const fields = keptFields(scenarioId);
    if (fields !== null) {
      setRunFields(fields);
    }
    begin(
      asked,
      {
        from: scenarioId,
        schemaVersion: schema_version,
        history: begun(installation),
        saved: null,
      },
      `Opened ${installation.name} from a scenario file; not saved yet.`,
    );
  }

  /** An installation's file opened as a draft not saved: a draft of its
   * identifier is left as it is kept, and a save of this one is refused until
   * it is renamed. */
  function beginImported(
    asked: number,
    { installation, schema_version }: Assessed,
    fileName: string,
    known: readonly DraftListed[] | null = drafts,
  ): void {
    begin(
      asked,
      { schemaVersion: schema_version, history: begun(installation), saved: null },
      `Imported ${installation.name} from ${fileName}; not saved yet.`,
      known,
    );
  }

  /** An installation's file the start page was given. The drafts are asked
   * for here too: the page has only just opened, and has not listed them. */
  async function openUploadedHouse(installationId: string): Promise<void> {
    const asked = nextSession();
    const kept = keptHouse(installationId);
    if (kept === null) {
      setStatus(`The file of ${installationId} is not kept in this window: import it here.`);
      return;
    }
    setBusy(true);
    const [answer, listed] = await Promise.all([assess(kept.text), loadDrafts()]);
    setBusy(false);
    if (!answer.ok) {
      if (session.current === asked) {
        setStatus(`${kept.fileName} cannot be opened: ${answer.problem}`);
      }
      return;
    }
    const known = listed.status === "loaded" ? listed.value : null;
    beginImported(asked, answer.value, kept.fileName, known);
  }

  /** A file opened as the start page's upload opens one: the simulator says
   * which kind it is, and a scenario file's run settings come with it. */
  async function importFile(file: File): Promise<void> {
    const asked = nextSession();
    const answer = await uploadFile(file);
    if (session.current !== asked) {
      return;
    }
    if (!answer.ok) {
      setStatus(answer.problem);
      return;
    }
    if (answer.value.kind === "installation") {
      beginImported(asked, answer.value.assessed, file.name);
      return;
    }
    const { scenario, settings, missingWeather } = answer.value;
    if (scenario === null) {
      setStatus(missingWeatherProblem(file.name, missingWeather));
      return;
    }
    keepSettings(scenario.id, settings);
    await openUploaded(scenario.id);
  }

  function startAgain(): void {
    if (unsaved(editing) && !window.confirm("Leave this draft? What is not saved is lost.")) {
      return;
    }
    nextSession();
    setEditing(null);
    setChosen(new Set());
    setRan(null);
    setRunFields(FIRST_RUN);
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

  /** An edit of many items, made by the simulator on the draft shown, and
   * kept as one step to undo; dropped if the draft has changed since it
   * was asked for, so that no edit is lost under another. */
  async function change(asked: Edit, said: string): Promise<void> {
    if (editing === null) {
      return;
    }
    const session_ = session.current;
    const sent = editing.history.present;
    setBusy(true);
    editsUnderWay.current += 1;
    const answer = await editItems(editing.schemaVersion, sent, asked).finally(() => {
      editsUnderWay.current -= 1;
    });
    setBusy(false);
    if (session.current !== session_) {
      return;
    }
    if (!answer.ok) {
      setStatus(`Not changed: ${answer.problem}`);
      return;
    }
    if (shown.current?.history.present !== sent) {
      setStatus("The draft changed while that edit was on its way: make it again.");
      return;
    }
    setEditing((now) =>
      now === null || now.history.present !== sent
        ? now
        : { ...now, history: edited(now.history, answer.value.installation) },
    );
    setRan(null);
    setStatus(said);
  }

  function rename(draftId: string, name: string): void {
    edit((installation) => ({ ...installation, installation_id: draftId, name }));
    setStatus(`Called ${name} (${draftId}).`);
  }

  function step(move: typeof undone): void {
    setEditing((now) => (now === null ? now : { ...now, history: move(now.history) }));
  }

  /** The draft shown saved as its next revision: which revision, and the
   * house it holds, or none if it was not saved. */
  async function save(): Promise<Kept | null> {
    if (editing === null) {
      return null;
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
      return null;
    }
    if (!answer.ok) {
      setStatus(`It is not saved: ${answer.problem}`);
      return null;
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
    return { draftId: draft.draft_id, revision: draft.revision, house: sent };
  }

  /** The revision to run: the one saved, or the draft saved now if it
   * holds what is not. */
  async function saved(): Promise<Kept | null> {
    if (editing === null) {
      return null;
    }
    if (editing.saved !== null && madeOn(editing) !== null && !unsaved(editing)) {
      const { draftId, revision } = editing.saved;
      return { draftId, revision, house: editing.history.present };
    }
    return save();
  }

  /** Whether the draft shown is the house that was saved: an edit made while
   * the save was on its way is kept unsaved, and no finishing action may
   * leave without it. */
  function stillSaved(kept: Kept): boolean {
    return shown.current !== null && same(shown.current.history.present, kept.house);
  }

  async function saveAndGoBack(): Promise<void> {
    const asked = session.current;
    const kept = await saved();
    if (kept === null || session.current !== asked) {
      return;
    }
    if (!stillSaved(kept)) {
      setStatus("The draft changed while it was being saved: save it again before leaving.");
      return;
    }
    navigate(LANDING_PATH);
  }

  /** The draft saved, run as a scenario of its own under the settings of the
   * run step, and a run of it started and followed. */
  async function saveAndStartRun(): Promise<void> {
    const settings = settingsOf(runFields);
    if (settings === null) {
      setStatus("The run step holds no run: give a date, whole days of one or more and a seed.");
      return;
    }
    const asked = session.current;
    const kept = await saved();
    if (kept === null || session.current !== asked) {
      return;
    }
    if (!stillSaved(kept)) {
      setStatus("The draft changed while it was being saved: save it again to run it.");
      return;
    }
    setBusy(true);
    const registered = await runDraft(kept.draftId, kept.revision, settings);
    // Left for another draft meanwhile: no run is started for this one.
    if (session.current !== asked) {
      setBusy(false);
      return;
    }
    if (!registered.ok) {
      setBusy(false);
      setStatus(`It does not run: ${registered.problem}`);
      return;
    }
    const started = await startRun(registered.value.id, {
      seed: "",
      secondsPerDay: DEFAULT_PACE_S,
    });
    setBusy(false);
    if (session.current !== asked) {
      return;
    }
    if (!started.ok) {
      setRan({ scenarioId: registered.value.id, name: registered.value.name });
      setStatus(
        `Its run is registered as ${registered.value.id}, but not started: ${started.problem}`,
      );
      return;
    }
    navigate(replayAddress(started.value.run_id, started.value.epoch, true));
  }

  function exportFile(): void {
    if (editing === null) {
      return;
    }
    if (editsUnderWay.current > 0) {
      setStatus("Not downloaded: an edit is still being made. Download the file once it is.");
      return;
    }
    const present = editing.history.present;
    offerFile(
      `${present.installation_id}${HOUSE_FILE_SUFFIX}`,
      installationFile(editing.schemaVersion, present),
    );
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

  // The items an error names, outlined on the house; the one item chosen,
  // drawn selected; and an item clicked in the view, chosen alone.
  const prefix = snapshot === null ? "" : `${snapshot.greenhouse_id}_`;
  const named = new Set(
    assessment.status === "assessed"
      ? assessment.findings.flatMap((found) => (found.severity === "error" ? found.items : []))
      : [],
  );
  const outlined: OverlayPrimitive[] = (snapshot?.entities ?? [])
    .filter((entity) => named.has(entity.entity_id.slice(prefix.length)))
    .map((entity) => ({
      id: `finding-${entity.entity_id}`,
      kind: "box",
      bounds: entityBounds(entity),
      color: FINDING_COLOR,
    }));
  const [only] = chosen.size === 1 ? [...chosen] : [];
  // A pipe run is drawn as its pipes, a rail as its tubes: a click on one
  // chooses the run or the rail, which is drawn selected by its first.
  const drawn = present === null ? new Map<string, string[]>() : drawnAs(present);
  const drawing = new Map([...drawn].flatMap(([item, parts]) => parts.map((part) => [part, item])));
  function picked(entityId: string | null): void {
    const id = entityId?.startsWith(prefix) ? entityId.slice(prefix.length) : null;
    const item = id === null ? undefined : drawing.get(id);
    setChosen(new Set(item === undefined ? [] : [item]));
  }

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

  // Starting a run saves first, so only what stops a run for good stops it.
  const startWhy =
    assessment.status !== "assessed"
      ? "It is not assessed yet."
      : assessment.findings.some((found) => found.severity === "error")
        ? "Its errors stop it running."
        : settingsOf(runFields) === null
          ? "The run step holds no run: give a date, whole days of one or more and a seed."
          : "";

  return (
    <main className="builder">
      <div className="builder-side">
        <header className="builder-bar">
          <div className="panel-head">
            <HomeButton />
            <h1>Setup builder</h1>
          </div>
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
              <button type="button" disabled={busy} onClick={exportFile}>
                Download house file
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
              </a>{" "}
              <a href={newRunAddress(ran.scenarioId)}>Start a run of it</a>{" "}
              <a href={LANDING_PATH}>Back to the start</a>
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
            <Inspector
              installation={editing.history.present}
              chosen={null}
              busy={busy}
              onEdit={(asked, said) => void change(asked, said)}
            />
            <Findings assessment={assessment} />
            <RowCrops installation={editing.history.present} onGive={give} />
            <Items
              installation={editing.history.present}
              snapshot={snapshot}
              chosen={chosen}
              busy={busy}
              onChoose={setChosen}
              onEdit={(asked, said) => void change(asked, said)}
            >
              {only !== undefined && (
                <Inspector
                  installation={editing.history.present}
                  chosen={only}
                  busy={busy}
                  onEdit={(asked, said) => void change(asked, said)}
                />
              )}
            </Items>
            <RunStep
              weathers={listed[0]?.weathers ?? []}
              disabled={runWhy !== "" || busy}
              why={runWhy}
              fields={runFields}
              onFields={setRunFields}
              onRun={(settings) => void run(settings)}
            />
            {ran !== null && <ShareScenario key={ran.scenarioId} scenarioId={ran.scenarioId} />}
            {editing.from !== undefined && (
              <p className="builder-note" data-testid="builder-uploaded-note">
                This draft was opened from a scenario file. While its identifier is the file's, a
                run made here keeps the file's weather and site, unless the run step names others.
                Given another identifier, it runs under the default weather and site. To run the
                file as it is, <a href={newRunAddress(editing.from)}>start a run of it</a>.
              </p>
            )}
            <FinishStep
              busy={busy}
              startWhy={startWhy}
              onGoBack={() => void saveAndGoBack()}
              onStartRun={() => void saveAndStartRun()}
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
            selectedId={only === undefined ? null : `${prefix}${drawn.get(only)?.[0] ?? only}`}
            overlays={outlined}
            onSelect={picked}
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
