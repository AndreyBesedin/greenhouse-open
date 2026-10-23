import { useRef, useState } from "react";

import { daysEnded } from "../clock";
import type { RunParts } from "../scene/run";
import { useLoad } from "../useLoad";
import {
  CHECKPOINTS_URL,
  type CheckpointMade,
  type CheckpointSummary,
  downloadName,
  downloadUrl,
  loadCheckpoints,
  saveCheckpoint,
  saveUrl,
  uploadCheckpoint,
} from "./checkpoints";

/** A checkpoint in words: its day, and the commands its run gave. */
export function describeCheckpoint(checkpoint: CheckpointSummary): string {
  const commands = checkpoint.commands.length;
  const daily =
    checkpoint.daily === null
      ? "its scenario's daily commands"
      : `${checkpoint.daily.length} daily commands`;
  const weather = checkpoint.weather === "default" ? "" : `, under ${checkpoint.weather}`;
  return `day ${checkpoint.day}: ${commands} commands before it, ${daily}${weather}`;
}

/**
 * A scenario's checkpoints (P09.5), opened on demand: save the start of the
 * moment's day, list those kept for the scenario, restore one, its run at
 * its moment, download one as JSON and upload one again, and compare one's
 * run with the run drawn. A checkpoint restored, given other commands from
 * its moment on, is a branch from it.
 */
export function CheckpointsPanel({
  scenarioId,
  run,
  time,
  onRestore,
  compared = null,
  onCompare,
  fetchFn = fetch,
}: {
  scenarioId: string;
  /** The run drawn, asked for as its climate is. */
  run: RunParts;
  /** The moment drawn, in seconds into the run. */
  time: number;
  onRestore: (checkpoint: CheckpointSummary) => void;
  /** The checkpoint whose run is compared with the run drawn, if one is. */
  compared?: string | null;
  /** Compares a checkpoint's run with the run drawn, or, given none, stops. */
  onCompare?: (checkpoint: CheckpointSummary | null) => void;
  fetchFn?: typeof fetch;
}) {
  const [open, setOpen] = useState(false);
  // Asked for again after each checkpoint made.
  const [made, setMade] = useState(0);
  const [working, setWorking] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const state = useLoad(
    open ? { url: CHECKPOINTS_URL, made } : null,
    ({ url }, given) => loadCheckpoints(url, given),
    { key: ({ url, made: count }) => `${url}#${count}`, fetch: fetchFn },
  );
  const day = daysEnded(time);

  async function make(doing: string, making: Promise<CheckpointMade>): Promise<void> {
    setWorking(doing);
    setProblem(null);
    const answer = await making;
    setWorking(null);
    if (answer.ok) {
      setMade((count) => count + 1);
    } else {
      setProblem(answer.problem);
    }
  }

  const kept =
    state.status === "loaded"
      ? state.checkpoints.filter((checkpoint) => checkpoint.scenarioId === scenarioId)
      : [];
  return (
    <details
      className="checkpoints"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Checkpoints</summary>
      <button
        type="button"
        disabled={working !== null}
        onClick={() =>
          void make(`Saving day ${day}'s start…`, saveCheckpoint(saveUrl(scenarioId, run), fetchFn))
        }
      >
        Save day {day}'s start
      </button>{" "}
      {/* The browser draws its own file picker's button and status in its own
          language: the viewer's button, in its words, opens it instead (#303). */}
      <button type="button" disabled={working !== null} onClick={() => picker.current?.click()}>
        Upload a checkpoint
      </button>
      <input
        ref={picker}
        type="file"
        accept="application/json,.json"
        hidden
        tabIndex={-1}
        aria-hidden
        disabled={working !== null}
        onChange={(event) => {
          const input = event.currentTarget;
          const file = input.files?.[0];
          if (file !== undefined) {
            void file.text().then((text) => make("Uploading…", uploadCheckpoint(text, fetchFn)));
          }
          // The same file chosen again is uploaded again.
          input.value = "";
        }}
      />
      {working !== null && <p data-testid="checkpoints-working">{working}</p>}
      {problem !== null && (
        <p role="alert" data-testid="checkpoints-problem">
          {problem}
        </p>
      )}
      {state.status === "unavailable" && (
        <p role="alert">The checkpoints cannot be listed: {state.reason}.</p>
      )}
      {state.status === "loaded" && kept.length === 0 && <p>None kept for this scenario.</p>}
      {kept.length > 0 && (
        <ol>
          {kept.map((checkpoint) => (
            <li key={checkpoint.checkpointId} data-testid="checkpoint">
              <span data-testid="checkpoint-description">{describeCheckpoint(checkpoint)}</span>{" "}
              <button
                type="button"
                aria-label={`Restore day ${checkpoint.day}, ${checkpoint.checkpointId}`}
                onClick={() => onRestore(checkpoint)}
              >
                Restore
              </button>{" "}
              {onCompare !== undefined && (
                <button
                  type="button"
                  aria-pressed={compared === checkpoint.checkpointId}
                  aria-label={`Compare with day ${checkpoint.day}, ${checkpoint.checkpointId}`}
                  onClick={() =>
                    onCompare(compared === checkpoint.checkpointId ? null : checkpoint)
                  }
                >
                  Compare
                </button>
              )}{" "}
              <a href={downloadUrl(checkpoint)} download={downloadName(checkpoint)}>
                Download
              </a>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}
