import { HomeButton } from "../landing/HomeButton";
import { STATUS_LABEL } from "../landing/storedRuns";
import type { PositionState } from "./position";

/** The run, in words: whose it is, at which seed, and which epoch. The
 * store keeps every epoch whole until a store can keep only the present. */
export function runSubtitle(position: PositionState): string {
  const seed = position.seed === null ? "the scenario's seed" : `seed ${position.seed}`;
  return `${seed} · epoch ${position.epoch} · everything kept`;
}

/**
 * Where the replay's header says what is replayed (P17.6): the way home, the
 * run's name, its seed and epoch, in what state it is (a word, never a
 * colour alone), and the way to its other runs.
 */
export function ReplayHeader({
  name,
  position,
  otherRunsHref,
}: {
  /** The scenario's name, once the list of scenarios has said it. */
  name: string | null;
  position: PositionState;
  otherRunsHref: string;
}) {
  return (
    <header className="replay-header">
      <HomeButton />
      <div className="replay-title">
        <h1>{name ?? position.scenario_id}</h1>
        <p data-testid="replay-subtitle">{runSubtitle(position)}</p>
      </div>
      <span
        className={`landing-status landing-status-${position.status}`}
        data-testid="replay-status"
      >
        {STATUS_LABEL[position.status]}
      </span>
      <span className="replay-spacer" />
      <a href={otherRunsHref} className="replay-back">
        Other runs
      </a>
    </header>
  );
}
