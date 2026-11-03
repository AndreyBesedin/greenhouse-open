import { HomeButton } from "../landing/HomeButton";
import { replayAddress } from "../landing/paths";
import { STATUS_LABEL } from "../landing/storedRuns";
import { whyNoFork } from "./fork";
import type { PositionState } from "./position";
import { dayLabel } from "./timeline";

/** The run, in words: whose it is, at which seed, and which epoch. The
 * store keeps every epoch whole until a store can keep only the present. */
export function runSubtitle(position: PositionState): string {
  const seed = position.seed === null ? "the scenario's seed" : `seed ${position.seed}`;
  const kept = `${seed} · epoch ${position.epoch} · everything kept`;
  const fork = position.fork;
  return fork === null
    ? kept
    : `${kept} · forked from epoch ${fork.epoch} at ${dayLabel(fork.at_s)}`;
}

/**
 * Where the replay's header says what is replayed (P17.6): the way home, the
 * run's name, its seed and epoch, in what state it is (a word, never a
 * colour alone), and the way to its other runs; and a fork of the run from
 * the moment shown (P17.8), or why there can be none.
 */
export function ReplayHeader({
  name,
  position,
  otherRunsHref,
  forking = false,
  forkRefused = null,
  onFork,
}: {
  /** The scenario's name, once the list of scenarios has said it. */
  name: string | null;
  position: PositionState;
  otherRunsHref: string;
  forking?: boolean;
  /** Why the simulator did not make the last fork asked for. */
  forkRefused?: string | null;
  onFork: () => void;
}) {
  const noFork = whyNoFork(position);
  return (
    <header className="replay-header">
      <HomeButton />
      <div className="replay-title">
        <h1>{name ?? position.scenario_id}</h1>
        <p data-testid="replay-subtitle">{runSubtitle(position)}</p>
        {noFork !== null && <p data-testid="replay-no-fork">{noFork}</p>}
        {forkRefused !== null && (
          <p role="alert" data-testid="replay-fork-refused">
            This run could not be forked: {forkRefused}.
          </p>
        )}
      </div>
      <span
        className={`landing-status landing-status-${position.status}`}
        data-testid="replay-status"
      >
        {STATUS_LABEL[position.status]}
      </span>
      <span className="replay-spacer" />
      {position.fork !== null && (
        <a href={replayAddress(position.fork.run_id, position.fork.epoch)} className="replay-back">
          The run it came from
        </a>
      )}
      <button
        type="button"
        className="replay-button"
        data-testid="replay-fork"
        disabled={forking || noFork !== null}
        onClick={onFork}
      >
        {forking ? "Forking…" : "Fork from here"}
      </button>
      <a href={otherRunsHref} className="replay-back">
        Other runs
      </a>
    </header>
  );
}
