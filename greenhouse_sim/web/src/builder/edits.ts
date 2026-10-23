/**
 * Edits of many parts of a draft at once (P12.2), as the simulator makes
 * them (`builder.batch`): each changes all it is asked to, or nothing, and
 * returns a new installation, so that the one before stays for an undo.
 */

import type { CropModel, Installation } from "./generated/assessedTypes";

/** The crop a row grows. */
export interface Crop {
  crop_model: CropModel;
  variety: string;
}

/** The numbers of an installation's crop rows, from 1. */
export function rowNumbers(installation: Installation): number[] {
  const rows = installation.layout.crop_rows?.rows ?? 0;
  return Array.from({ length: rows }, (_, index) => index + 1);
}

/** An installation whose chosen rows grow `crop`, every other row as
 * before; refused, changing nothing, if no row is chosen, a row is not one
 * of its layout's, or the variety is not named. */
export function withCrop(
  installation: Installation,
  rows: readonly number[],
  crop: Crop,
): Installation {
  const known = new Set(rowNumbers(installation));
  if (rows.length === 0) {
    throw new Error("choose at least one row");
  }
  if (rows.some((row) => !known.has(row))) {
    throw new Error(`choose rows from 1 to ${known.size}`);
  }
  if (crop.variety.trim() === "") {
    throw new Error("name the variety");
  }
  const crops = new Map(installation.row_crops.map((each) => [each.row, each]));
  for (const row of rows) {
    crops.set(row, { row, ...crop });
  }
  return {
    ...installation,
    row_crops: [...crops.values()].sort((a, b) => a.row - b.row),
  };
}
