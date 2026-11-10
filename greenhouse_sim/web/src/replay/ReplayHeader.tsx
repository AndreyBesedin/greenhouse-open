import { useRef, useState } from "react";

import { Button } from "../design/Button";
import { LinkButton } from "../design/LinkButton";
import { Notice } from "../design/Notice";
import { StatusChip } from "../design/StatusChip";
import { HomeButton } from "../landing/HomeButton";
import { replayAddress } from "../landing/paths";
import { RunDelete } from "../landing/RunDelete";
import { STATUS_TONE } from "../landing/RunParts";
import { deleteRun, notDeleted } from "../landing/runActions";
import { isComputing, STATUS_LABEL, type Status } from "../landing/storedRuns";
import { failedText } from "./failure";
import { whyNoFork } from "./fork";
import type { PositionState } from "./position";
import { forkedText } from "./timeline";
import { useForkQuestion } from "./useForkQuestion";

/** What the run's status is named, to whoever hears the page, which is told each
 * change of it. */
export const STATUS_NAME = "Run status";

/** What the header's buttons say on hover (P22.9); Delete says the start page's. */
export const FORK_NOTE = "Make a new run from this moment; asks first";
export const PARENT_NOTE = "Open the run this one was forked from";

/** The run, in words: whose it is, at which seed, and which epoch. The
 * store keeps every epoch whole until a store can keep only the present; of a
 * failed one, what it computed before it failed. */
export function runSubtitle(position: PositionState): string {
  const seed = position.seed === null ? "the scenario's seed" : `seed ${position.seed}`;
  const whole = position.status === "failed" ? "kept to where it failed" : "everything kept";
  const kept = `${seed} · epoch ${position.epoch} · ${whole}`;
  const fork = position.fork;
  return fork === null ? kept : `${kept} · ${forkedText(fork)}`;
}

/**
 * Where the replay's header says what is replayed (P17.6): the way home, the
 * run's name, its seed and epoch, in what state it is (a word, never a
 * colour alone) and, if it failed, why; a fork of the run from the moment
 * shown (P17.8), asked first, or why there can be none; and the run's Delete
 * (P22.9), the start page's, asked first, after which the page is gone with the
 * run (`onDeleted`).
 */
export function ReplayHeader({
  name,
  position,
  forking = false,
  forkRefused = null,
  failure = null,
  onFork,
  onDeleted,
}: {
  /** The scenario's name, once the list of scenarios has said it. */
  name: string | null;
  position: PositionState;
  forking?: boolean;
  /** Why the simulator did not make the last fork asked for. */
  forkRefused?: string | null;
  /** Why a failed run failed, once the simulator has said. */
  failure?: string | null;
  onFork: () => void;
  onDeleted: () => void;
}) {
  const noFork = whyNoFork(position);
  const { trigger, ask, question } = useForkQuestion({ size: "target" });
  const heading = useRef<HTMLHeadingElement>(null);
  // Why the run was not deleted, said while the run stands as it was asked about.
  const [notGone, setNotGone] = useState<{ why: string; status: Status } | null>(null);

  async function remove(): Promise<boolean> {
    const answer = await deleteRun(position);
    if (answer !== "stopping" && answer.ok) {
      setNotGone(null);
      onDeleted();
      return true;
    }
    const why = answer === "stopping" ? notDeleted(position, "this run") : answer.problem;
    setNotGone({ why, status: position.status });
    return false;
  }

  const deleteRefused = notGone?.status === position.status ? notGone.why : null;
  return (
    <header className="replay-header">
      <HomeButton />
      <div className="replay-title">
        <h1 ref={heading}>Run of {name ?? position.scenario_id}</h1>
        <p data-testid="replay-subtitle">{runSubtitle(position)}</p>
        {position.status === "failed" && <p data-testid="replay-failed">{failedText(failure)}</p>}
        {noFork !== null && <p data-testid="replay-no-fork">{noFork}</p>}
        {forkRefused !== null && (
          <Notice kind="problem" data-testid="replay-fork-refused">
            This run could not be forked: {forkRefused}.
          </Notice>
        )}
        {deleteRefused !== null && (
          <Notice kind="problem" data-testid="replay-delete-refused">
            {deleteRefused}
          </Notice>
        )}
      </div>
      <StatusChip tone={STATUS_TONE[position.status]} label={STATUS_NAME}>
        {STATUS_LABEL[position.status]}
      </StatusChip>
      <span className="replay-spacer" />
      {position.fork !== null && position.parent_kept && (
        <LinkButton
          href={replayAddress(position.fork.run_id, position.fork.epoch)}
          title={PARENT_NOTE}
        >
          The run it came from
        </LinkButton>
      )}
      <Button
        ref={trigger}
        data-testid="replay-fork"
        title={FORK_NOTE}
        disabled={forking || noFork !== null}
        onClick={() => ask(onFork)}
      >
        {forking ? "Forking…" : "Fork from here"}
      </Button>
      <RunDelete
        name="this run"
        computing={isComputing(position)}
        onDelete={remove}
        whenGone={heading}
      />
      {question}
    </header>
  );
}
