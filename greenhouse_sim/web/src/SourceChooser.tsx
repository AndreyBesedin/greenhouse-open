import { useState } from "react";

import { FIRST_LAB_RUN } from "./plants/lab";
import { DEFAULT_STRESS_PLANTS } from "./qa/stressScene";
import { ScenarioList } from "./ScenarioList";
import { SceneStatus } from "./SceneStatus";
import { DEFAULT_LAYOUT, openingMoment, type ScenariosState } from "./scenarios";
import type { SceneSource, SceneState } from "./scene/source";

/** A scene or the plant lab, to be chosen by name. */
interface Choice {
  label: string;
  source: SceneSource;
}

/** The scenes drawn without a run, to check the renderer. */
const TEST_SCENES: readonly Choice[] = [
  { label: "Empty grid", source: { kind: "reference" } },
  { label: "Example scene", source: { kind: "example" } },
  { label: "Fixture gallery", source: { kind: "fixtures" } },
  { label: "Stress scene", source: { kind: "stress", plants: DEFAULT_STRESS_PLANTS } },
];

/** The plant model alone. */
const LABS: readonly Choice[] = [
  { label: "Plant lab", source: { kind: "plants", ...FIRST_LAB_RUN } },
];

/** The choices whose label holds `filter`, whatever its case. */
function matching(choices: readonly Choice[], filter: string): readonly Choice[] {
  const wanted = filter.trim().toLowerCase();
  return choices.filter((choice) => choice.label.toLowerCase().includes(wanted));
}

/**
 * What the viewer shows, and the choice of it (#201): folded, one line that
 * says what is shown, or why it is not; opened, the simulator's scenarios,
 * each opened here or played live, the test scenes and the plant lab, each
 * group saying what it is, and a filter over all of them. It folds again
 * once something is chosen. A choice is a new page in the browser's history
 * (`useSource`), so Back returns to the view before.
 */
export function SourceChooser({
  scenarios,
  source,
  scene,
  initiallyOpen = false,
  onSource,
}: {
  scenarios: ScenariosState;
  source: SceneSource;
  scene: SceneState;
  /** Whether it starts open, as it does when nothing has been chosen yet. */
  initiallyOpen?: boolean;
  onSource: (source: SceneSource) => void;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const [filter, setFilter] = useState("");
  const choose = (chosen: SceneSource) => {
    setOpen(false);
    onSource(chosen);
  };
  const scenes = matching(TEST_SCENES, filter);
  const labs = matching(LABS, filter);

  return (
    <details
      className="source-chooser"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <SceneStatus source={source} state={scene} />
      </summary>
      <input
        type="search"
        aria-label="Filter scenarios and scenes"
        placeholder="Filter: name, id or description"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <section aria-label="Scenarios">
        <p className="chooser-note">
          Greenhouses the simulator runs through days: their climate, crop and sensors.
        </p>
        <ScenarioList
          state={scenarios}
          filter={filter}
          shownLayout={
            source.kind === "scenario"
              ? { scenarioId: source.scenarioId, layout: source.layout ?? DEFAULT_LAYOUT }
              : null
          }
          onShow={(scenarioId, layout) =>
            choose({
              kind: "scenario",
              scenarioId,
              ...(layout === undefined || layout === DEFAULT_LAYOUT ? {} : { layout }),
              // Opened afresh, a scenario with an opening day opens there.
              ...(layout === undefined
                ? (openingMoment(
                    scenarios.status === "loaded"
                      ? scenarios.scenarios.find((s) => s.id === scenarioId)
                      : undefined,
                  ) ?? {})
                : {}),
            })
          }
          onLive={(scenarioId) => choose({ kind: "live", scenarioId })}
          onFollow={(scenarioId) =>
            choose({ kind: "scenario", scenarioId, field: "climate", follow: true })
          }
        />
      </section>
      <Group
        name="Test scenes"
        note="Drawn without a run, to check the renderer."
        choices={scenes}
        onChoose={choose}
      />
      <Group
        name="Plant lab"
        note="The plant model alone: a row of plants by day and seed."
        choices={labs}
        onChoose={choose}
      />
      <p className="chooser-note">
        Open: its run here, from its start or its opening day. Live: the simulator plays it a day a
        second, the same for every viewer. Follow: its own run as it is played back, the run a
        consumer reads. Back returns to the view before.
      </p>
    </details>
  );
}

/** A group of choices under its name, unless the filter leaves none. */
function Group({
  name,
  note,
  choices,
  onChoose,
}: {
  name: string;
  note: string;
  choices: readonly Choice[];
  onChoose: (source: SceneSource) => void;
}) {
  if (choices.length === 0) {
    return null;
  }
  return (
    <section aria-label={name}>
      <h2>{name}</h2>
      <p className="chooser-note">{note}</p>
      <p className="chooser-choices">
        {choices.map((choice) => (
          <button type="button" key={choice.label} onClick={() => onChoose(choice.source)}>
            {choice.label}
          </button>
        ))}
      </p>
    </section>
  );
}
