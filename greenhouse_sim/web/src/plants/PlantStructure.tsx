import { useEffect, useState } from "react";

import { loadPlantStructure, type OrganNode, type StructureState } from "./structure";

function Organ({
  organ,
  selectedId,
  onSelect,
}: {
  organ: OrganNode;
  selectedId: string | null;
  onSelect: (organId: string) => void;
}) {
  const name = organ.drawn ? (
    <button
      type="button"
      className="organ-link"
      aria-pressed={organ.id === selectedId}
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
            <Organ key={child.id} organ={child} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** The plant lab's plant, organ by organ, as a debug tree: every organ with
 * its kind, thermal age and stage. An organ the view draws can be selected
 * from here, as it can by clicking it. */
export function PlantStructure({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (organId: string) => void;
}) {
  const [state, setState] = useState<StructureState>({ status: "loading" });

  useEffect(() => {
    let current = true;
    void loadPlantStructure().then((loaded) => {
      if (current) {
        setState(loaded);
      }
    });
    return () => {
      current = false;
    };
  }, []);

  switch (state.status) {
    case "loading":
      return <p>Loading the plant's structure…</p>;
    case "unavailable":
      return <p role="alert">The plant's structure is not available: {state.reason}.</p>;
    case "loaded":
      return (
        <details className="plant-structure" open>
          <summary>Plant structure</summary>
          <ul>
            <Organ organ={state.tree} selectedId={selectedId} onSelect={onSelect} />
          </ul>
        </details>
      );
  }
}
