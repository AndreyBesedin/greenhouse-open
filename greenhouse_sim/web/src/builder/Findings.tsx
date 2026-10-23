import { useId } from "react";

import type { Finding } from "./generated/assessedTypes";

/** What the simulator says a draft needs: its findings, or why it could
 * not say; nothing while it is being asked. */
export type Assessment =
  | { status: "asked" }
  | { status: "assessed"; findings: readonly Finding[] }
  | { status: "failed"; problem: string };

/** What stops a draft running, and what it lacks: a sentence on whether it
 * runs, then each finding, errors first. Until the simulator answers, or
 * if it cannot, it says so rather than show the findings of an edit
 * before. */
export function Findings({ assessment }: { assessment: Assessment }) {
  const heading = useId();
  if (assessment.status !== "assessed") {
    return (
      <section className="builder-findings" aria-labelledby={heading}>
        <h2 id={heading}>What it needs</h2>
        <p data-testid="builder-runnable">
          {assessment.status === "asked"
            ? "Being assessed…"
            : `It cannot be assessed: ${assessment.problem}`}
        </p>
      </section>
    );
  }
  const errors = assessment.findings.filter((found) => found.severity === "error");
  const warnings = assessment.findings.filter((found) => found.severity === "warning");
  return (
    <section className="builder-findings" aria-labelledby={heading}>
      <h2 id={heading}>What it needs</h2>
      <p data-testid="builder-runnable">
        {errors.length === 0
          ? "It can run."
          : `${errors.length === 1 ? "One error stops" : `${errors.length} errors stop`} it running.`}
      </p>
      {assessment.findings.length > 0 && (
        <ul>
          {[...errors, ...warnings].map((found) => (
            <li
              key={found.code}
              className={`builder-finding-${found.severity}`}
              data-code={found.code}
            >
              <strong>{found.severity === "error" ? "Error" : "Warning"}:</strong> {found.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
