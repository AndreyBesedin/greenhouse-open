import { type FormEvent, useId, useState } from "react";

import { type Crop, rowNumbers } from "./edits";
import type { CropModel, Installation } from "./generated/assessedTypes";

const MODELS: readonly CropModel[] = ["simple", "organ"];

/**
 * The crop each row grows, and one crop given to many rows at once (P12.2):
 * rows are chosen by their boxes, all of them at once by the first, and
 * given the crop below in one edit, undone in one step.
 */
export function RowCrops({
  installation,
  onGive,
}: {
  installation: Installation;
  onGive: (rows: number[], crop: Crop) => void;
}) {
  const heading = useId();
  const rows = rowNumbers(installation);
  const crops = new Map(installation.row_crops.map((each) => [each.row, each]));
  const [chosen, setChosen] = useState<ReadonlySet<number>>(new Set());
  const [model, setModel] = useState<CropModel>("simple");
  const [variety, setVariety] = useState("cherry_tomato");
  const all = rows.length > 0 && rows.every((row) => chosen.has(row));

  function choose(row: number, on: boolean): void {
    const next = new Set(chosen);
    if (on) {
      next.add(row);
    } else {
      next.delete(row);
    }
    setChosen(next);
  }

  function give(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onGive(
      rows.filter((row) => chosen.has(row)),
      { crop_model: model, variety },
    );
  }

  return (
    <section className="builder-rows" aria-labelledby={heading}>
      <h2 id={heading}>Rows</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">
              <input
                type="checkbox"
                aria-label="Choose every row"
                checked={all}
                onChange={(event) => setChosen(new Set(event.target.checked ? rows : []))}
              />
            </th>
            <th scope="col">Row</th>
            <th scope="col">Crop model</th>
            <th scope="col">Variety</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row}>
              <td>
                <input
                  type="checkbox"
                  aria-label={`Choose row ${row}`}
                  checked={chosen.has(row)}
                  onChange={(event) => choose(row, event.target.checked)}
                />
              </td>
              <td>{row}</td>
              <td>{crops.get(row)?.crop_model ?? "none"}</td>
              <td>{crops.get(row)?.variety ?? "none"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="builder-give" onSubmit={give}>
        <label className="builder-give-field">
          <span>Crop model</span>
          <select value={model} onChange={(event) => setModel(event.target.value as CropModel)}>
            {MODELS.map((each) => (
              <option key={each} value={each}>
                {each}
              </option>
            ))}
          </select>
        </label>
        <label className="builder-give-field">
          <span>Variety</span>
          <input value={variety} onChange={(event) => setVariety(event.target.value)} />
        </label>
        <button type="submit" disabled={chosen.size === 0}>
          Give the chosen rows this crop
        </button>
      </form>
    </section>
  );
}
