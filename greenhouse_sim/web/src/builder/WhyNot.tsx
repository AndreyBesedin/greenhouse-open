import type { Assessment } from "./Findings";

/** Why a button cannot be used now, each reason a sentence, the simulator's
 * or the builder's; none if it can be. */
export type Reasons = readonly string[];

/** Why a house cannot be saved as a new draft under `draftId`: a draft of
 * that identifier is kept already, which a save would otherwise overwrite. */
export function keptAlready(draftId: string): string {
  return (
    `A draft with the identifier ${draftId} is kept already: give this one another ` +
    "identifier, or open that draft to change it."
  );
}

/** What in a draft's assessment stops it running: the simulator not having
 * answered yet, or not able to, or each error it finds, in its words. */
export function whatStopsARun(assessment: Assessment): string[] {
  if (assessment.status === "asked") {
    return ["It is not assessed yet."];
  }
  if (assessment.status === "failed") {
    return [`It cannot be assessed: ${assessment.problem}`];
  }
  return assessment.findings
    .filter((found) => found.severity === "error")
    .map((found) => found.message);
}

/**
 * Beside a button that cannot be used now, why not: `lead`, then the one
 * reason, or each of several in a list; nothing if there is none. The button
 * names it as its description (`aria-describedby`, by `id`), so that what it
 * says is read with the button, not only in the list of findings or the
 * status line.
 */
export function WhyNot({
  id,
  lead,
  reasons,
  testId,
}: {
  id: string;
  lead: string;
  reasons: Reasons;
  testId?: string;
}) {
  if (reasons.length === 0) {
    return null;
  }
  if (reasons.length === 1) {
    return (
      <p id={id} className="builder-why" data-testid={testId}>
        {lead} {reasons[0]}
      </p>
    );
  }
  return (
    <div id={id} className="builder-why" data-testid={testId}>
      <p>{lead}</p>
      <ul>
        {reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}

/** A button's description, its reasons' `id` while it has any. */
export function describedBy(id: string, reasons: Reasons): string | undefined {
  return reasons.length > 0 ? id : undefined;
}
