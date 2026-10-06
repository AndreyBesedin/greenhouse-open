import { CATEGORY_COLORS, CATEGORY_LABELS, type EnvelopeCategory } from "./categories";

/** What each colour means in the categories' debug view. */
export function CategoryLegend({ categories }: { categories: readonly EnvelopeCategory[] }) {
  return (
    <figure className="category-legend" aria-label="Surface categories">
      <figcaption>Surface categories</figcaption>
      <ul>
        {categories.map((category) => (
          <li key={category} data-testid="category">
            <span className="swatch" style={{ background: CATEGORY_COLORS[category] }} />
            {CATEGORY_LABELS[category]}
          </li>
        ))}
      </ul>
    </figure>
  );
}
