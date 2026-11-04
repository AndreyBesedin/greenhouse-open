import { useEffect, useId, useRef, useState } from "react";

/** What a fork does, said before one is made: it takes a worker and makes a run. */
export const WHAT_A_FORK_DOES =
  "A new run from this moment, computed by a worker beside the others. This one stays as it is.";

function ForkQuestion({
  buttonClass,
  onFork,
  onCancel,
}: {
  buttonClass: string;
  onFork: () => void;
  onCancel: () => void;
}) {
  const said = useId();
  const yes = useRef<HTMLButtonElement>(null);
  useEffect(() => yes.current?.focus(), []);
  return (
    <fieldset
      className="replay-fork-question"
      aria-labelledby={said}
      data-testid="fork-question"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          // Handled: the view's own Escape, on the window, finds it done.
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <p id={said}>{WHAT_A_FORK_DOES}</p>
      <button
        ref={yes}
        type="button"
        className={`${buttonClass} landing-button-primary`}
        onClick={onFork}
      >
        Make the fork
      </button>
      <button type="button" className={buttonClass} onClick={onCancel}>
        Cancel
      </button>
    </fieldset>
  );
}

/**
 * A fork asks first, in the page: `ask`, from what was pressed (`trigger`), shows
 * `question`, which makes the fork or goes back to what was pressed.
 *
 * The fork is the one asked for: a replay goes on playing behind the question, and
 * it still takes the moment that was shown when it was asked. `about` says what it
 * would be made with: once that changes it is no longer what was asked about, and
 * the question goes.
 */
export function useForkQuestion({
  about = "",
  buttonClass = "",
}: {
  about?: string;
  /** How its buttons are drawn, where the page's are drawn by a class. */
  buttonClass?: string;
} = {}) {
  const [asked, setAsked] = useState<{ fork: () => void; about: string } | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  if (asked !== null && asked.about !== about) {
    setAsked(null);
  }
  function answered(): void {
    setAsked(null);
    trigger.current?.focus();
  }
  return {
    trigger,
    ask: (fork: () => void) => setAsked({ fork, about }),
    question:
      asked === null ? null : (
        <ForkQuestion
          buttonClass={buttonClass}
          onFork={() => {
            answered();
            asked.fork();
          }}
          onCancel={answered}
        />
      ),
  };
}
