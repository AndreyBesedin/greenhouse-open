import { type ReactNode, useId } from "react";

/**
 * An outlined, titled card of the info panel's sections on one topic
 * (#306): the simulation, the house, its equipment, the weather outside. Its
 * title sits on its outline, so that a card costs the panel next to no
 * height; its sections fold as before.
 */
export function PanelCard({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section className="panel-card" aria-labelledby={id}>
      <h2 id={id} className="panel-card-title">
        {title}
      </h2>
      {children}
    </section>
  );
}
