import { useMemo } from "react";

import { ALL_OVERLAYS, selectionOverlays } from "../debug/overlays";
import { ScalarLegend } from "../debug/ScalarLegend";
import { colouringBy } from "../debug/scalar";
import { selectedEntity } from "../selection";
import { Viewport } from "../Viewport";
import { QA_COLOUR_PROPERTY, QA_SELECTED_ID, qaSeed } from "./qaPage";
import { qaScene } from "./qaScene";

const ignore = () => undefined;

/**
 * The canonical page for the renderer's screenshot tests: the QA scene for a
 * seed, from the default camera, with a plant selected, every overlay drawn
 * and the plants coloured by height. Nothing on it changes over time, so it
 * looks the same on every visit; the HUD and panels, whose readings do
 * change, are left out.
 */
export function QaRenderer({ search }: { search: string }) {
  const seed = qaSeed(search);
  const snapshot = useMemo(() => (seed === null ? null : qaScene(seed)), [seed]);
  const overlays = useMemo(() => {
    const selected = selectedEntity(snapshot, QA_SELECTED_ID);
    return selected === null ? [] : selectionOverlays(selected, ALL_OVERLAYS);
  }, [snapshot]);
  const colouring = useMemo(
    () => (snapshot === null ? null : colouringBy(snapshot, QA_COLOUR_PROPERTY)),
    [snapshot],
  );

  if (seed === null || snapshot === null) {
    return (
      <p className="qa-caption" role="alert">
        The seed must be a whole number, such as ?seed=42.
      </p>
    );
  }
  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={null}
        selectedId={QA_SELECTED_ID}
        colouring={colouring}
        overlays={overlays}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      />
      <p className="qa-caption" data-testid="qa-caption">
        Renderer QA, seed {seed}
      </p>
      <div className="legends">{colouring && <ScalarLegend colouring={colouring} />}</div>
    </main>
  );
}
