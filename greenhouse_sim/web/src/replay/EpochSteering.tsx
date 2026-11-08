import { dayLabel } from "./timeline";

/** What steering a running epoch from its replay does, said before a change. */
export const WHAT_STEERING_DOES =
  "This run is being computed: a target or a level set here is given to it, from the moment its worker has reached, not the one shown, and nothing forks.";
/** What a change does once the epoch steered has ended. */
export const ENDED_STEERING =
  "This run is no longer computed: a target or a level set here now makes a fork of it.";

/** Where the latest change given to a running epoch stands, in words. */
export function steeringText({
  waiting,
  taken,
}: {
  waiting: boolean;
  taken: number | null;
}): string | null {
  if (waiting) {
    return "Asked of the run: waiting for its worker to take it.";
  }
  return taken === null ? null : `The run took the latest change from ${dayLabel(taken)}.`;
}

/**
 * The replay of a running epoch steered from its panels (P22.1, decision 0073):
 * what a change does, where the latest stands, and, if the simulator or the
 * epoch's worker refused it, why, in their words.
 */
export function EpochSteering({
  computing = true,
  waiting,
  taken,
  refusal,
}: {
  /** Whether the epoch is still being computed, and takes changes. */
  computing?: boolean;
  /** Whether a change is on its way to the epoch's worker. */
  waiting: boolean;
  /** The moment the latest change taken took effect from, in seconds into the run. */
  taken: number | null;
  /** Why the latest change was not made, if it was not. */
  refusal: string | null;
}) {
  const standing = steeringText({ waiting, taken });
  // A refusal stands until the next change is answered.
  const refused = waiting ? null : refusal;
  return (
    <div data-testid="epoch-steering">
      <p className="targets-note">{computing ? WHAT_STEERING_DOES : ENDED_STEERING}</p>
      <p className="targets-note" role="status" data-testid="epoch-steering-status">
        {refused === null ? standing : null}
      </p>
      {refused !== null && (
        <p className="targets-note" role="alert" data-testid="epoch-steering-refused">
          Not changed: {refused}.
        </p>
      )}
    </div>
  );
}
