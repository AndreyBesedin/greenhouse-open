import { PERCENT } from "./units";

/** A piece of equipment or an opening, as a panel lists it: its name in the scene,
 * the kind it is, and how far it runs or stands open, from 0 to 1. */
export interface Grouped {
  label: string;
  kind: string;
  level: number;
}

/** Pieces of one kind, under the kind's name, each named by what tells it from the
 * others of its kind: the fans' `right` and `left`, the roof vents' `1`, `2`, `3`. */
export interface Group<Piece extends Grouped> {
  /** The kind in words, `fans` or `door`, plural for more than one. */
  name: string;
  pieces: { piece: Piece; name: string }[];
}

/** The kind of a piece in words: `roof_vent` is `roof vent`. */
function kindWords(kind: string): string {
  return kind.replaceAll("_", " ");
}

/** What tells a piece from the others of its kind: its name less its kind's words,
 * or its whole name if that leaves nothing. */
function ownName(label: string, kind: string): string {
  const words = kindWords(kind);
  const rest = label.toLowerCase().startsWith(words) ? label.slice(words.length).trim() : label;
  return rest === "" ? label : rest;
}

/** The pieces in groups by kind, each group where its first piece stands. */
export function inGroups<Piece extends Grouped>(pieces: readonly Piece[]): Group<Piece>[] {
  const kinds = [...new Set(pieces.map(({ kind }) => kind))];
  return kinds.map((kind) => {
    const ofKind = pieces.filter((piece) => piece.kind === kind);
    const words = kindWords(kind);
    return {
      name: ofKind.length > 1 ? `${words}s` : words,
      pieces: ofKind.map((piece) => ({
        piece,
        name: ofKind.length > 1 ? ownName(piece.label, kind) : piece.label,
      })),
    };
  });
}

/** A level in a line, `100%`. */
export function percent(level: number): string {
  return `${Math.round(level * PERCENT)}%`;
}

/** The groups in a line, those running and those not: a group whose pieces all run
 * at one level by its name, `fans 100%`; otherwise each piece by its own, `fan right
 * 100%`, and among those not running, `fan left`. */
export function describeGroups<Piece extends Grouped>(
  groups: readonly Group<Piece>[],
): { running: string[]; idle: string[] } {
  const running: string[] = [];
  const idle: string[] = [];
  for (const group of groups) {
    const levels = new Set(group.pieces.map(({ piece }) => piece.level));
    const [level] = levels;
    if (levels.size === 1 && level !== undefined) {
      (level > 0 ? running : idle).push(level > 0 ? `${group.name} ${percent(level)}` : group.name);
      continue;
    }
    for (const { piece } of group.pieces) {
      (piece.level > 0 ? running : idle).push(
        piece.level > 0 ? `${piece.label} ${percent(piece.level)}` : piece.label,
      );
    }
  }
  return { running, idle };
}

/** A group's name at the head of its rows: `Fans`. */
export function capitalised(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}
