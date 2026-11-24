import { useId } from "react";

import { Button } from "../design/Button";
import { Notice } from "../design/Notice";
import { describedBy, type Reasons, WhyNot } from "./WhyNot";

/**
 * How a person leaves the builder once the house is as they want it (P17.11):
 * back to the start page, or into a run of it. Each saves what is not saved.
 * Below the buttons, why either cannot be used now, each reason in full, and
 * why the simulator refused the last one pressed.
 */
export function FinishStep({
  busy,
  goBackReasons,
  startReasons,
  refused,
  onGoBack,
  onStartRun,
}: {
  busy: boolean;
  /** Why the draft cannot be saved now, or none. */
  goBackReasons: Reasons;
  /** Why a run cannot be started now, or none. */
  startReasons: Reasons;
  /** Why the simulator refused the last of them pressed, if it did. */
  refused?: string | undefined;
  onGoBack: () => void;
  onStartRun: () => void;
}) {
  const goBackWhy = useId();
  const startWhy = useId();
  // The reasons that stop both are said once, under the first.
  const startOnly = startReasons.filter((reason) => !goBackReasons.includes(reason));
  return (
    <section className="builder-finish" aria-label="Finish">
      <div className="builder-finish-buttons">
        <Button
          disabled={busy || goBackReasons.length > 0}
          aria-describedby={describedBy(goBackWhy, goBackReasons)}
          onClick={onGoBack}
        >
          Save and go back
        </Button>
        <Button
          disabled={busy || startReasons.length > 0}
          aria-describedby={
            [describedBy(goBackWhy, goBackReasons), describedBy(startWhy, startOnly)]
              .filter((each) => each !== undefined)
              .join(" ") || undefined
          }
          onClick={onStartRun}
        >
          Save and start a run
        </Button>
      </div>
      <WhyNot
        id={goBackWhy}
        lead="It cannot be saved:"
        reasons={goBackReasons}
        testId="builder-finish-save-why"
      />
      <WhyNot
        id={startWhy}
        lead="A run cannot be started:"
        reasons={startOnly}
        testId="builder-finish-start-why"
      />
      {refused !== undefined && (
        <Notice kind="problem" className="builder-refused" data-testid="builder-finish-refused">
          {refused}
        </Notice>
      )}
    </section>
  );
}
