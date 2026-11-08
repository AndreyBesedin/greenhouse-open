/** What a status says by its colour beside its words: `active` is under way or
 * waiting to be, `problem` stopped short of its end. */
export type StatusTone = "plain" | "active" | "problem";

export interface StatusChipProps {
  tone?: StatusTone | undefined;
  /** Its words, which say the status: never a colour alone. */
  children: string;
  /** More of what it means, shown on hover and said to whoever hears the page. */
  note?: string | undefined;
  /** The class a page places it by. */
  className?: string | undefined;
}

/** A status, in words, drawn as a chip of its tone. */
export function StatusChip({ tone = "plain", children, note, className }: StatusChipProps) {
  const toned = tone === "plain" ? "ds-status-chip" : `ds-status-chip ds-status-chip-${tone}`;
  return (
    <span className={className === undefined ? toned : `${toned} ${className}`} title={note}>
      {children}
      {note !== undefined && <span className="visually-hidden"> {note}</span>}
    </span>
  );
}
