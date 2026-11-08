import { type ReactNode, useId } from "react";

/** What a field's control is given, so that its label names it and its hint and
 * problem describe it. */
export interface FieldControl {
  id: string;
  "aria-describedby": string | undefined;
  "aria-invalid": true | undefined;
}

export interface FieldProps {
  /** Its name, which its control is called by. */
  label: string;
  /** What it takes, under its control. */
  hint?: string | undefined;
  /** Why what it holds is refused, under its hint; its control is then invalid. */
  problem?: string | undefined;
  /** Draws its control, which takes what it is given. */
  children: (control: FieldControl) => ReactNode;
  /** The class a page places it by. */
  className?: string | undefined;
}

/**
 * A label, its control, and a hint or a problem below. The label stands beside the
 * control, not around it, so that the hint and the problem describe the control
 * and are not part of its name.
 */
export function Field({ label, hint, problem, children, className }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const problemId = `${id}-problem`;
  const describedBy = [hint === undefined ? "" : hintId, problem === undefined ? "" : problemId]
    .filter((part) => part !== "")
    .join(" ");
  return (
    <div className={className === undefined ? "ds-field" : `ds-field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {children({
        id,
        "aria-describedby": describedBy === "" ? undefined : describedBy,
        "aria-invalid": problem === undefined ? undefined : true,
      })}
      {hint !== undefined && (
        <p id={hintId} className="ds-field-hint">
          {hint}
        </p>
      )}
      {problem !== undefined && (
        <p id={problemId} className="ds-field-problem">
          {problem}
        </p>
      )}
    </div>
  );
}
