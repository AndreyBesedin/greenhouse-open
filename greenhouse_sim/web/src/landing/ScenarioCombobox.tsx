import { useId, useState } from "react";

import { scenarioMatches } from "../ScenarioList";
import type { ScenarioSummary } from "../scenarios";
import { runCountText } from "./storedRuns";

/** The entry after the scenarios, which builds one instead of choosing one. */
const BUILD = "build";

/**
 * The scenario to open, searched by name, identifier or description: an
 * editable combobox with a list (WAI-ARIA authoring practices), so that it
 * is chosen by keyboard as well as by pointer. Each scenario shows how many
 * runs it has kept; the last entry builds a new scenario.
 */
export function ScenarioCombobox({
  scenarios,
  counts,
  onChoose,
  onBuild,
}: {
  scenarios: readonly ScenarioSummary[];
  /** How many runs each scenario has kept, once they are known. */
  counts: ReadonlyMap<string, number> | null;
  onChoose: (scenarioId: string) => void;
  onBuild: () => void;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listed = scenarios.filter((scenario) => scenarioMatches(scenario, query));
  const entries: readonly (string | typeof BUILD)[] = [...listed.map((s) => s.id), BUILD];
  const last = entries.length - 1;
  const optionId = (index: number) => `${id}-option-${index}`;

  function choose(entry: string): void {
    setOpen(false);
    setQuery("");
    setActive(0);
    if (entry === BUILD) {
      onBuild();
    } else {
      onChoose(entry);
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>): void {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setOpen(true);
        setActive(open ? Math.min(active + 1, last) : active);
        break;
      case "ArrowUp":
        event.preventDefault();
        setActive(Math.max(active - 1, 0));
        break;
      case "Enter": {
        const entry = entries[active];
        if (open && entry !== undefined) {
          event.preventDefault();
          choose(entry);
        }
        break;
      }
      case "Escape":
        setOpen(false);
        break;
    }
  }

  return (
    <div className="landing-combobox">
      <label htmlFor={`${id}-input`} className="landing-label">
        Scenario
      </label>
      <input
        id={`${id}-input`}
        type="text"
        className="landing-input"
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={open ? optionId(active) : undefined}
        autoComplete="off"
        placeholder="Search scenarios"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        // Focus is already there after a choice or Escape: a click opens the list again.
        onClick={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && (
        // Chosen on mouse down, which comes before the input loses focus and
        // closes the list.
        <ul
          id={`${id}-list`}
          // biome-ignore lint/a11y/noNoninteractiveElementToInteractiveRole: the editable combobox pattern (WAI-ARIA): the list is read through aria-activedescendant while focus stays on the input, so its options take no focus.
          role="listbox"
          aria-label="Scenarios"
          className="landing-options"
        >
          {listed.map((scenario, index) => (
            // biome-ignore lint/a11y/useFocusableInteractive: an option of the same list takes no focus: the input keeps it.
            <li
              key={scenario.id}
              id={optionId(index)}
              // biome-ignore lint/a11y/noNoninteractiveElementToInteractiveRole: an option of the same list.
              role="option"
              aria-selected={index === active}
              className="landing-option"
              onMouseDown={(event) => {
                event.preventDefault();
                choose(scenario.id);
              }}
            >
              <span className="landing-option-line">
                <strong>{scenario.name}</strong>
                {counts !== null && <span>{runCountText(counts.get(scenario.id) ?? 0)}</span>}
              </span>
              <span className="landing-option-note">
                {scenario.id} · {scenario.description}
              </span>
            </li>
          ))}
          {listed.length === 0 && (
            <li role="presentation" className="landing-option-none">
              No scenario matches “{query.trim()}”.
            </li>
          )}
          {/* biome-ignore lint/a11y/useFocusableInteractive: an option of the same list takes no focus: the input keeps it. */}
          <li
            id={optionId(listed.length)}
            // biome-ignore lint/a11y/noNoninteractiveElementToInteractiveRole: an option of the same list.
            role="option"
            aria-selected={listed.length === active}
            className="landing-option landing-option-build"
            onMouseDown={(event) => {
              event.preventDefault();
              choose(BUILD);
            }}
          >
            Build a new scenario
          </li>
        </ul>
      )}
    </div>
  );
}
