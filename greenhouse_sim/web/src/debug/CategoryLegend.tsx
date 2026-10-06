import { CATEGORY_COLORS, CATEGORY_LABELS, type Category, isEnvelopeCategory } from "./categories";

function Legend({
  name,
  categories,
  testId,
}: {
  name: string;
  categories: readonly Category[];
  testId: string;
}) {
  return (
    <figure className="category-legend" aria-label={name}>
      <figcaption>{name}</figcaption>
      <ul>
        {categories.map((category) => (
          <li key={category} data-testid={testId}>
            <span className="swatch" style={{ background: CATEGORY_COLORS[category] }} />
            {CATEGORY_LABELS[category]}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** What each colour means in the categories' debug view: one legend for the
 * envelope's surfaces and one for the layout, each shown when the scene has
 * any of its categories. */
export function CategoryLegend({ categories }: { categories: readonly Category[] }) {
  const envelope = categories.filter(isEnvelopeCategory);
  const layout = categories.filter((category) => !isEnvelopeCategory(category));
  return (
    <>
      {envelope.length > 0 && (
        <Legend name="Surface categories" categories={envelope} testId="category" />
      )}
      {layout.length > 0 && (
        <Legend name="Layout categories" categories={layout} testId="layout-category" />
      )}
    </>
  );
}
