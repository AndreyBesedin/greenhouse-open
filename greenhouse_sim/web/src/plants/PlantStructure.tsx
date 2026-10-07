import { useEffect, useState } from "react";

import { labRunQuery } from "./lab";
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
  plant: { plantId, ...run },
  selectedOrgan,
  onSelect,
}: {
  /** The plant it shows, on a run of the lab. */
  plant: LabPlant;
  /** The organ the selected entity draws part of. */
  selectedOrgan: string | null;
  onSelect: (organId: string) => void;
}) {
  const [state, setState] = useState<StructureState>({ status: "loading" });

  // Asked for by its query, which changes only when the run does.
  const query = labRunQuery(run);
  // Another run's or plant's tree stays on show until this one's arrives.
  useEffect(() => {
    let current = true;
    void loadPlantStructure(plantId, query).then((loaded) => {
      if (current) {
        setState(loaded);
      }
    });
    return () => {
      current = false;
    };
  }, [plantId, query]);

  switch (state.status) {
    case "loading":
      return <p>Loading the plant's structure…</p>;
    case "unavailable":
      return <p role="alert">The plant's structure is not available: {state.reason}.</p>;
    case "loaded":
      return (
        <>
          <details className="plant-structure" open>
            <summary>Plant structure: {plantId}</summary>
            <ul>
              <Organ organ={state.tree} selectedOrgan={selectedOrgan} onSelect={onSelect} />
            </ul>
          </details>
          {state.history.length > 0 && (
            <details className="plant-history" open>
              <summary>History: {plantId}</summary>
              <ol>
                {state.history.map((event, index) => (
                  <li
                    // The history only grows, so an event keeps its place.
                    // biome-ignore lint/suspicious/noArrayIndexKey: see above
                    key={index}
                    data-testid="plant-event"
                    className={event.applied ? undefined : "refused"}
                  >
                    at {Math.round(event.thermalTime)} °Cd: {event.applied ? "" : "refused, "}
                    {event.note}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      );
  }
}
