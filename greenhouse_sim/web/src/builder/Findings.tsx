import { useId } from "react";

import type { Finding } from "./generated/assessedTypes";

/** What stops a draft running, and what it lacks: a sentence on whether it
 * runs, then each finding, errors first, with the rows it concerns. */
export function Findings({ findings }: { findings: readonly Finding[] }) {
  const heading = useId();
  const errors = findings.filter((found) => found.severity === "error");
  const warnings = findings.filter((found) => found.severity === "warning");
  return (
    <section className="builder-findings" aria-labelledby={heading}>
      <h2 id={heading}>What it needs</h2>
      <p data-testid="builder-runnable">
        {errors.length === 0
          ? "It can run."
          : `${errors.length === 1 ? "One error stops" : `${errors.length} errors stop`} it running.`}
      </p>
      {findings.length > 0 && (
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
