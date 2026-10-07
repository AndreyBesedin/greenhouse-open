import { CFD_COLORS, CFD_LABELS, categorySummary } from "./boundaries";
import type { CfdGeometry } from "./generated/geometryTypes";

/** What each colour of the CFD boundaries means, and how much of the mesh
 * each category takes. */
export function CfdLegend({ geometry }: { geometry: CfdGeometry }) {
  return (
    <figure className="category-legend" aria-label="CFD boundaries">
      <figcaption>CFD boundaries</figcaption>
      <ul>
        {categorySummary(geometry).map(({ category, boundaries, meshFaces }) => (
          <li key={category} data-testid="cfd-category">
            <span className="swatch" style={{ background: CFD_COLORS[category] }} />
            {CFD_LABELS[category]}
            {boundaries > 1 ? ` ×${boundaries}` : ""}:{" "}
            {category === "obstacle" ? `${meshFaces} cells` : `${meshFaces} faces`}
          </li>
        ))}
      </ul>
    </figure>
  );
}
