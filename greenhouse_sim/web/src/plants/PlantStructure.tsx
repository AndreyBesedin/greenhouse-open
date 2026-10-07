import { useEffect, useState } from "react";

import {
  type LabPlant,
  loadPlantStructure,
  type OrganNode,
  type StructureState,
} from "./structure";

function Organ({
  organ,
  selectedOrgan,
  onSelect,
}: {
  organ: OrganNode;
  selectedOrgan: string | null;
  onSelect: (organId: string) => void;
}) {
  const name = organ.drawn ? (
    <button
      type="button"
      className="organ-link"
      aria-pressed={organ.id === selectedOrgan}
      onClick={() => onSelect(organ.id)}
    >
      {organ.id}
    </button>
  ) : (
    <span>{organ.id}</span>
  );
  return (
    <li data-testid="organ" data-organ-kind={organ.kind}>
      {name}{" "}
      <span className="organ-detail">
        {organ.kind}, {organ.detail}
      </span>
      {organ.children.length > 0 && (
        <ul>
          {organ.children.map((child) => (
            <Organ key={child.id} organ={child} selectedOrgan={selectedOrgan} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** One of the plant lab's plants, organ by organ, as a debug tree: every
 * organ with its kind, thermal age and stage. An organ the view draws can be
 * selected from here, as it can by clicking any part of it. */
export function PlantStructure({
  plant: { plantId, day, seed },
  selectedOrgan,
  onSelect,
}: {
  /** The plant it shows, on a day of the lab's run, from a seed. */
  plant: LabPlant;
  /** The organ the selected entity draws part of. */
  selectedOrgan: string | null;
  onSelect: (organId: string) => void;
}) {
  const [state, setState] = useState<StructureState>({ status: "loading" });

  // Another day's or plant's tree stays on show until this one's arrives.
  useEffect(() => {
    let current = true;
    void loadPlantStructure({ plantId, day, seed }).then((loaded) => {
      if (current) {
        setState(loaded);
      }
    });
    return () => {
      current = false;
    };
  }, [plantId, day, seed]);

  switch (state.status) {
    case "loading":
      return <p>Loading the plant's structure…</p>;
    case "unavailable":
      return <p role="alert">The plant's structure is not available: {state.reason}.</p>;
    case "loaded":
      return (
        <details className="plant-structure" open>
          <summary>Plant structure: {plantId}</summary>
          <ul>
            <Organ organ={state.tree} selectedOrgan={selectedOrgan} onSelect={onSelect} />
          </ul>
        </details>
      );
  }
}
