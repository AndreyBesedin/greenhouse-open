import { changesQuery, type SceneSource } from "../scene/source";
import { useLoad } from "../useLoad";
import { cfdGeometryUrl, loadCfdGeometry } from "./geometry";

/** The boundaries a CFD solver is given, changed as the scene is, while a
 * scenario's view asks to draw them; the last stays on show until the next
 * arrives. How hard its equipment runs does not change them. */
export function useCfdBoundaries(source: SceneSource) {
  return useLoad(
    source.kind === "scenario" && source.cfdBoundaries
      ? cfdGeometryUrl(source.scenarioId, changesQuery({ ...source, levels: {} }, "?"))
      : null,
    loadCfdGeometry,
  );
}
