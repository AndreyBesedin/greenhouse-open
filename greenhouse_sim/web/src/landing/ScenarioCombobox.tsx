import { useEffect, useId, useRef, useState } from "react";

import { scenariosMatching } from "../ScenarioList";
import type { ScenarioSummary } from "../scenarios";
import { runCountText } from "./storedRuns";

/** What an entry of the list does: opens a scenario, or, as the last one,
 * builds one. Tagged, since no scenario identifier is reserved. */
type Entry = { kind: "scenario"; id: string } | { kind: "build" };

/** Where an options list is scrolled to, so that an option shows in it: where
 * it is if it already does, else the least that brings it to the near edge. */
export function scrolledTo(
  list: { scrollTop: number; clientHeight: number },
  option: { offsetTop: number; offsetHeight: number },
): number {
  if (option.offsetTop < list.scrollTop) {
    return option.offsetTop;
  }
  const bottom = option.offsetTop + option.offsetHeight;
  return bottom > list.scrollTop + list.clientHeight ? bottom - list.clientHeight : list.scrollTop;
}

/**
 * The scenario to open, searched by name, identifier or description: an
 * editable combobox with a list (WAI-ARIA authoring practices), so that it
 * is chosen by keyboard as well as by pointer. Each scenario shows how many
 * runs it has kept; the last entry builds a new scenario.
 */
export function ScenarioCombobox({
  scenarios,
  counts,
  behindDialog = false,
  onChoose,
  onBuild,
}: {
  scenarios: readonly ScenarioSummary[];
  /** How many runs each scenario has kept, once they are known. */
  counts: ReadonlyMap<string, number> | null;
  /** Whether a dialog it opened is showing: closing, the browser gives the input
   * focus back, which is no asking for the list. */
  behindDialog?: boolean;
  onChoose: (scenarioId: string) => void;
  onBuild: () => void;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listed = scenariosMatching(scenarios, query);
  const entries: readonly Entry[] = [
    ...listed.map((scenario): Entry => ({ kind: "scenario", id: scenario.id })),
    { kind: "build" },
  ];
  const last = entries.length - 1;
  const optionId = (index: number) => `${id}-option-${index}`;
  const options = useRef<HTMLUListElement>(null);

  // The input keeps focus, so the active option is brought into view in the
  // list itself, and not the page.
  useEffect(() => {
    const list = options.current;
    const option = open ? document.getElementById(`${id}-option-${active}`) : null;
    if (list !== null && option !== null && list.contains(option)) {
      list.scrollTop = scrolledTo(list, option);
    }
  }, [open, active, id]);

  function choose(entry: Entry): void {
    setOpen(false);
    setQuery("");
    setActive(0);
    if (entry.kind === "build") {
      onBuild();
    } else {
      onChoose(entry.id);
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
        onFocus={() => setOpen(!behindDialog)}
        // Focus is already there after a choice or Escape: a click opens the list again.
        onClick={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && (
        // Chosen on mouse down, which comes before the input loses focus and
        // closes the list.
        <ul
          ref={options}
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
                choose({ kind: "scenario", id: scenario.id });
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
              choose({ kind: "build" });
            }}
          >
            Build a new scenario
          </li>
        </ul>
      )}
    </div>
  );
}
