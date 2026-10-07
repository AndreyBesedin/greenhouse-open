import type { CfdGeometryState } from "./geometry";

/** Whether the boundaries a CFD solver is given are drawn over the scenario,
 * and what they are. */
export function CfdControls({
  shown,
  state,
  onShow,
}: {
  shown: boolean;
  state: CfdGeometryState;
  onShow: (show: boolean) => void;
}) {
  return (
    <fieldset className="cfd-controls" aria-label="CFD">
      <label>
        <input type="checkbox" checked={shown} onChange={(event) => onShow(event.target.checked)} />{" "}
        CFD boundaries
      </label>
      {shown && <p data-testid="cfd-status">{describeState(state)}</p>}
    </fieldset>
  );
}

function counted(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function describeState(state: CfdGeometryState): string {
  switch (state.status) {
    case "none":
      return "No CFD boundaries drawn.";
    case "loading":
      return "Loading the CFD boundaries…";
    case "unavailable":
      return `The CFD boundaries are not available: ${state.reason}.`;
    case "rejected":
      return `The CFD boundaries were refused: ${state.problems.join("; ")}.`;
    case "loaded": {
      const { cells } = state.geometry.grid;
      const openings = state.geometry.boundaries.filter((b) => b.category === "opening");
      const obstacles = state.geometry.boundaries.filter((b) => b.category === "obstacle");
      const removed = obstacles.reduce((total, b) => total + b.mesh_faces, 0);
      const parts = [
        `${cells.x} × ${cells.y} × ${cells.z} cells`,
        counted(openings.length, "opening", "openings"),
        `${counted(obstacles.length, "obstacle", "obstacles")} removing ${counted(removed, "cell", "cells")}`,
      ];
      const { too_small: tooSmall, unplaced } = state.geometry;
      const notes = [
        ...(tooSmall.length === 0
          ? []
          : [`${counted(tooSmall.length, "fixture", "fixtures")} too small to remove a cell`]),
        ...(unplaced.length === 0 ? [] : [`no face left for ${unplaced.join(", ")}`]),
      ];
      return `${parts.join(", ")}${notes.length === 0 ? "" : `; ${notes.join("; ")}`}.`;
    }
  }
}
