import { type FormEvent, type ReactNode, useId, useState } from "react";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Installation } from "./generated/assessedTypes";
import type { Axis, Edit } from "./generated/editTypes";
import {
  FIXTURE_KINDS,
  hosts,
  hostsFor,
  ITEM_KINDS,
  type ItemKind,
  itemOf,
  listed,
  OPENING_KINDS,
  type OpeningKind,
  openingOf,
  startingCentre,
  startingPlace,
} from "./palette";

const AXES: readonly Axis[] = ["x", "y", "z"];
// How few items spacing takes: the two furthest apart stay, and the rest
// are spaced between them.
const FEWEST_TO_SPACE = 3;

/** What a number field holds, as typed. */
type Typed = Record<string, string>;

const number = (typed: Typed, name: string) => Number(typed[name]);

function NumberField({
  label,
  name,
  typed,
  onType,
  min,
}: {
  label: string;
  name: string;
  typed: Typed;
  onType: (name: string, value: string) => void;
  min?: number | undefined;
}) {
  return (
    <label className="builder-give-field">
      <span>{label}</span>
      <input
        type="number"
        step="any"
        required
        min={min}
        value={typed[name] ?? ""}
        onChange={(event) => onType(name, event.target.value)}
      />
    </label>
  );
}

/** A value as a field takes it: a number or true or false where it reads
 * as one, the text as typed otherwise, for the simulator to check. */
export function fieldValue(text: string): number | boolean | string {
  const trimmed = text.trim();
  if (trimmed === "true" || trimmed === "false") {
    return trimmed === "true";
  }
  const asNumber = Number(trimmed);
  return trimmed !== "" && Number.isFinite(asNumber) ? asNumber : text;
}

/**
 * The house's equipment, sensors, zones, fixtures, doors and vents,
 * placed, copied, spaced, changed and removed many at a time (P12.3). Each
 * is one edit the simulator makes and checks, undone in one step: the
 * palette places several at a step, or spreads doors and vents along each
 * surface chosen;
 * the items chosen in the list are copied at a step, spaced evenly, given
 * one value for a field or removed.
 */
export function Items({
  installation,
  snapshot,
  chosen,
  busy,
  onChoose,
  onEdit,
  children,
}: {
  installation: Installation;
  snapshot: SceneSnapshot | null;
  /** The items chosen, by their identifiers: here, or in the view. */
  chosen: ReadonlySet<string>;
  busy: boolean;
  onChoose: (chosen: ReadonlySet<string>) => void;
  onEdit: (edit: Edit, said: string) => void;
  /** What is shown of the items chosen, below their list: the inspector. */
  children?: ReactNode;
}) {
  const heading = useId();
  const items = listed(installation);
  const surfaces = snapshot === null ? [] : hosts(snapshot);
  const chosenNow = items.filter((item) => chosen.has(item.id));
  const all = items.length > 0 && items.every((item) => chosen.has(item.id));
  const [kind, setKind] = useState<ItemKind | OpeningKind>("fan");
  const isOpening = (OPENING_KINDS as readonly string[]).includes(kind);
  const [onSurfaces, setOnSurfaces] = useState<ReadonlySet<string>>(new Set());
  const [spread, setSpread] = useState(true);
  const [typed, setTyped] = useState<Typed>(() => placing("fan"));
  const [axis, setAxis] = useState<Axis>("x");
  const [path, setPath] = useState("");
  const [value, setValue] = useState("");

  function type(name: string, text: string): void {
    setTyped((now) => ({ ...now, [name]: text }));
  }

  /** The palette's fields for `next`, as it first places one. */
  function placing(next: ItemKind | OpeningKind, on: readonly string[] = []): Typed {
    const counts = {
      count: "1",
      stepX: "1",
      stepY: "0",
      stepZ: "0",
      copies: "1",
      copyX: "1",
      copyY: "0",
      copyZ: "0",
    };
    if ((OPENING_KINDS as readonly string[]).includes(next)) {
      const opening = openingOf(next as OpeningKind, "", { x: 0, y: 0 });
      const host = hostsFor(next as OpeningKind, surfaces).find((each) =>
        on.includes(each.surfaceId),
      );
      const centre =
        host === undefined
          ? { x: 0, y: 0 }
          : startingCentre(next as OpeningKind, opening.height, host);
      return {
        ...counts,
        count: "4",
        width: String(opening.width),
        height: String(opening.height),
        centreX: String(centre.x),
        centreY: String(centre.y),
        stepX: "2",
      };
    }
    const at = startingPlace(next as ItemKind);
    return { ...counts, x: String(at.x), y: String(at.y), z: String(at.z) };
  }

  function chooseKind(next: ItemKind | OpeningKind): void {
    setKind(next);
    setOnSurfaces(new Set());
    setTyped(placing(next));
  }

  function chooseSurface(surfaceId: string, on: boolean): void {
    const next = new Set(onSurfaces);
    if (on) {
      next.add(surfaceId);
    } else {
      next.delete(surfaceId);
    }
    setOnSurfaces(next);
    if (on && onSurfaces.size === 0) {
      // Its first surface sets where it first goes on each.
      const fresh = placing(kind, [surfaceId]);
      setTyped((now) => ({ ...now, centreX: fresh.centreX ?? "0", centreY: fresh.centreY ?? "0" }));
    }
  }

  function choose(id: string, on: boolean): void {
    const next = new Set(chosen);
    if (on) {
      next.add(id);
    } else {
      next.delete(id);
    }
    onChoose(next);
  }

  function place(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const count = number(typed, "count");
    if (!isOpening) {
      const at = { x: number(typed, "x"), y: number(typed, "y"), z: number(typed, "z") };
      const step = {
        x: number(typed, "stepX"),
        y: number(typed, "stepY"),
        z: number(typed, "stepZ"),
      };
      onEdit(
        { edit: "place_items", item: itemOf(kind as ItemKind, at), count, step },
        `Placed ${count} ${kind.replaceAll("_", " ")}${count === 1 ? "" : "s"}.`,
      );
      return;
    }
    const surfaceIds = [...onSurfaces];
    const opening = {
      ...openingOf(kind as OpeningKind, surfaceIds[0] ?? "", {
        x: number(typed, "centreX"),
        y: number(typed, "centreY"),
      }),
      width: number(typed, "width"),
      height: number(typed, "height"),
    };
    const what = `${kind.replaceAll("_", " ")}s on ${surfaceIds.length} surface${surfaceIds.length === 1 ? "" : "s"}`;
    onEdit(
      spread
        ? { edit: "spread_openings", opening, surfaces: surfaceIds, count }
        : {
            edit: "place_openings",
            opening,
            surfaces: surfaceIds,
            count,
            step: { x: number(typed, "stepX"), y: number(typed, "stepY") },
          },
      `Placed ${count} ${what}.`,
    );
  }

  const ids = chosenNow.map((item) => item.id);
  const ons = new Set(chosenNow.map((item) => item.on));
  const oneKind = ons.size === 1;
  const inHouse = ons.has("house");
  const named = ids.join(", ");

  function copy(): void {
    const count = number(typed, "copies");
    const x = number(typed, "copyX");
    const y = number(typed, "copyY");
    onEdit(
      inHouse
        ? { edit: "repeat_items", items: ids, count, step: { x, y, z: number(typed, "copyZ") } }
        : { edit: "repeat_openings", openings: ids, count, step: { x, y } },
      `Copied ${named} ${count} time${count === 1 ? "" : "s"}.`,
    );
  }

  function changed(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onEdit(
      { edit: "set_field", items: ids, path: path.trim(), value: fieldValue(value) },
      `Set ${path.trim()} of ${named}.`,
    );
  }

  const field = (label: string, name: string, min?: number): ReactNode => (
    <NumberField label={label} name={name} typed={typed} onType={type} min={min} />
  );

  return (
    <section className="builder-items" aria-labelledby={heading}>
      <h2 id={heading}>Items of the house</h2>
      {items.length === 0 ? (
        <p className="builder-note">None placed yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">
                <input
                  type="checkbox"
                  aria-label="Choose every item"
                  checked={all}
                  onChange={(event) =>
                    onChoose(new Set(event.target.checked ? items.map((item) => item.id) : []))
                  }
                />
              </th>
              <th scope="col">Item</th>
              <th scope="col">Kind</th>
              <th scope="col">Where</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Choose ${item.id}`}
                    checked={chosen.has(item.id)}
                    onChange={(event) => choose(item.id, event.target.checked)}
                  />
                </td>
                <td>{item.id}</td>
                <td>{item.kind.replaceAll("_", " ")}</td>
                <td>{item.where}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {children}
      {chosenNow.length > 0 && (
        <fieldset className="builder-chosen">
          <legend>With {named}</legend>
          {!oneKind ? (
            <p className="builder-note">
              Choose items in the house, or doors and vents, to copy or space them.
            </p>
          ) : (
            <>
              <div className="builder-give">
                {field("Copies of each", "copies", 1)}
                {field(inHouse ? "Step along x (m)" : "Step along (m)", "copyX")}
                {field(inHouse ? "Step along y (m)" : "Step up (m)", "copyY")}
                {inHouse && field("Step along z (m)", "copyZ")}
                <button type="button" disabled={busy} onClick={copy}>
                  Copy
                </button>
              </div>
              <div className="builder-give">
                {inHouse && (
                  <label className="builder-give-field">
                    <span>Axis</span>
                    <select value={axis} onChange={(event) => setAxis(event.target.value as Axis)}>
                      {AXES.map((each) => (
                        <option key={each} value={each}>
                          {each}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <button
                  type="button"
                  disabled={busy || ids.length < FEWEST_TO_SPACE}
                  onClick={() =>
                    onEdit(
                      inHouse
                        ? { edit: "space_items", items: ids, axis }
                        : { edit: "space_openings", openings: ids },
                      `Spaced ${named} evenly.`,
                    )
                  }
                >
                  Space evenly
                </button>
              </div>
            </>
          )}
          <form className="builder-give" onSubmit={changed}>
            <label className="builder-give-field">
              <span>Field</span>
              <input
                required
                placeholder="power_w, base.z"
                value={path}
                onChange={(event) => setPath(event.target.value)}
              />
            </label>
            <label className="builder-give-field">
              <span>Value</span>
              <input required value={value} onChange={(event) => setValue(event.target.value)} />
            </label>
            <button type="submit" disabled={busy}>
              Set it on each
            </button>
          </form>
          <button
            type="button"
            disabled={busy}
            onClick={() => onEdit({ edit: "remove_items", items: ids }, `Removed ${named}.`)}
          >
            Remove
          </button>
        </fieldset>
      )}

      <form className="builder-palette" aria-label="Place" onSubmit={place}>
        <h3>Place</h3>
        <label className="builder-give-field">
          <span>What</span>
          <select
            value={kind}
            onChange={(event) => chooseKind(event.target.value as ItemKind | OpeningKind)}
          >
            <optgroup label="In the house">
              {ITEM_KINDS.map((each) => (
                <option key={each} value={each}>
                  {each.replaceAll("_", " ")}
                </option>
              ))}
            </optgroup>
            <optgroup label="Zones and fixtures">
              {FIXTURE_KINDS.map((each) => (
                <option key={each} value={each}>
                  {each.replaceAll("_", " ")}
                </option>
              ))}
            </optgroup>
            <optgroup label="On a surface">
              {OPENING_KINDS.map((each) => (
                <option key={each} value={each}>
                  {each.replaceAll("_", " ")}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        {isOpening ? (
          <>
            <fieldset className="builder-surfaces">
              <legend>On</legend>
              {hostsFor(kind as OpeningKind, surfaces).map((host) => (
                <label key={host.surfaceId}>
                  <input
                    type="checkbox"
                    checked={onSurfaces.has(host.surfaceId)}
                    onChange={(event) => chooseSurface(host.surfaceId, event.target.checked)}
                  />
                  {host.surfaceId.replaceAll("_", " ")}
                </label>
              ))}
            </fieldset>
            {field("Width (m)", "width")}
            {field("Height (m)", "height")}
            {field("How many on each", "count", 1)}
            <label className="builder-give-field">
              <input
                type="checkbox"
                checked={spread}
                onChange={(event) => setSpread(event.target.checked)}
              />
              <span>Spread evenly along each</span>
            </label>
            {!spread && (
              <>
                {field("Centre along (m)", "centreX")}
                {field("Step along (m)", "stepX")}
              </>
            )}
            {field("Centre up (m)", "centreY")}
          </>
        ) : (
          <>
            {field("x (m)", "x")}
            {field("y (m)", "y")}
            {field("z (m)", "z")}
            {field("How many", "count", 1)}
            {field("Step along x (m)", "stepX")}
            {field("Step along y (m)", "stepY")}
            {field("Step along z (m)", "stepZ")}
          </>
        )}
        <button type="submit" disabled={busy || (isOpening && onSurfaces.size === 0)}>
          Place
        </button>
      </form>
    </section>
  );
}
