import { Button } from "../design/Button";

/**
 * How a person leaves the builder once the house is as they want it (P17.11):
 * back to the start page, or into a run of it. Each saves what is not saved.
 */
export function FinishStep({
  busy,
  startWhy,
  onGoBack,
  onStartRun,
}: {
  busy: boolean;
  /** Why a run cannot be started now, or nothing. */
  startWhy: string;
  onGoBack: () => void;
  onStartRun: () => void;
}) {
  return (
    <section className="builder-finish" aria-label="Finish">
      <div className="builder-finish-buttons">
        <Button disabled={busy} onClick={onGoBack}>
          Save and go back
        </Button>
        <Button disabled={busy || startWhy !== ""} onClick={onStartRun}>
          Save and start a run
        </Button>
      </div>
      {startWhy !== "" && <p className="builder-note">{startWhy}</p>}
    </section>
  );
}
