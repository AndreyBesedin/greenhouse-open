import { useLoad } from "../useLoad";
import { labRunQuery } from "./lab";
import {
  type LabPlant,
  loadPlantStructure,
  type OrganNode,
  type PlantEvent,
  plantStructureUrl,
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

/** A plant, organ by organ, as a debug tree: every organ with its kind,
 * thermal age and stage. An organ the view draws can be selected from
 * here, as it can by clicking any part of it. */
export function PlantTree({
  plantId,
  tree,
  selectedOrgan,
  onSelect,
}: {
  plantId: string;
  tree: OrganNode;
  /** The organ the selected entity draws part of. */
  selectedOrgan: string | null;
  onSelect: (organId: string) => void;
}) {
  return (
    <details className="plant-structure" open>
      <summary>Plant structure: {plantId}</summary>
      <ul>
        <Organ organ={tree} selectedOrgan={selectedOrgan} onSelect={onSelect} />
      </ul>
    </details>
  );
}

/** Everything done to a plant, or asked of it and refused, in order, at the
 * plant's thermal time; nothing if nothing was. */
export function PlantHistory({ plantId, history }: { plantId: string; history: PlantEvent[] }) {
  if (history.length === 0) {
    return null;
  }
  return (
    <details className="plant-history" open>
      <summary>History: {plantId}</summary>
      <ol>
        {history.map((event, index) => (
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
  );
}

/** One of the plant lab's plants, organ by organ, and its history. */
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
  // Asked for by its query, which changes only when the run does.
  const query = labRunQuery(run);
  // Another run's or plant's tree, loaded, stays on show until this one's arrives.
  const state = useLoad(plantStructureUrl(plantId, query), (_url, fetchFn) =>
    loadPlantStructure(plantId, query, fetchFn),
  );

  switch (state.status) {
    case "loading":
      return <p>Loading the plant's structure…</p>;
    case "unavailable":
      return <p role="alert">The plant's structure is not available: {state.reason}.</p>;
    case "loaded":
      return (
        <>
          <PlantTree
            plantId={plantId}
            tree={state.tree}
            selectedOrgan={selectedOrgan}
            onSelect={onSelect}
          />
          <PlantHistory plantId={plantId} history={state.history} />
        </>
      );
  }
}
