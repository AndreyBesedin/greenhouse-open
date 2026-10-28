"""Pins every reference scenario, run end to end, as the simulator behaves today.

`test_run_characterization.py` pins one small run in detail. This pins each
registered scenario as a caller would run it: every plant the scenario
describes, for its whole duration, as its days advance with no action
taken: a policy acts on the run, not on the engine's day (P13.9). Each
simulated day is reduced to three digests (hidden state, observations and
ground truth) and each run to a readable summary of where it ended.

A failure names the scenario, the first day that diverged and which of the
three parts moved, so a restructuring that is meant to preserve behaviour
shows exactly where it did not.

The hidden-state digest covers what the world is: sizes, stages, water,
harvest. It leaves out the random draws the simple model makes when it
creates a plant or a fruit (growth multipliers, target diameters, ripening
days), so moving those draws into model-specific state changes nothing here
unless their effect on the world changes.

Floats are rounded to six decimal places before hashing, so last-bit
differences between platforms' maths libraries are not mistaken for
behaviour.

The recorded values are a snapshot of current behaviour, not a
specification. When a deliberate change moves them, regenerate the fixture
from `greenhouse_sim/`:

    python tests/test_reference_baseline.py --update

and say why in the commit message.
"""

import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import cache
from pathlib import Path
from statistics import fmean

import pytest
from greenhouse_protocol.observation import Observation

from greenhouse_sim.domain.crop import FruitStatus
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import GroundTruth, ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import GreenhouseWorld

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reference_baseline.json"
SCENARIOS = sorted(SCENARIO_REGISTRY)
SIMULATION_ID = "sim_reference_baseline"
DECIMALS = 6
PARTS = ("state", "observations", "ground_truth")

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


@dataclass(frozen=True)
class Baseline:
    days: list[str]
    summary: dict[str, Json]


@cache
def _run(scenario_id: str) -> Baseline:
    config = SCENARIO_REGISTRY[scenario_id]
    engine = SimulationEngine(config)
    plant_count = config.rows * config.columns
    plant_ids = [f"{scenario_id}_plant_{i:03d}" for i in range(1, plant_count + 1)]
    world = engine.initialize(plant_ids, greenhouse_id=scenario_id)
    start = datetime.combine(config.start_date, time(12, 0), tzinfo=UTC)

    days: list[str] = []
    observations: list[Observation] = []
    truths: list[GroundTruth] = []

    for day in range(1, config.duration_days + 1):
        timestamp = start + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id=SIMULATION_ID)
        truth = ground_truth(
            step.world, timestamp=timestamp, water_capacity_ml=config.simple_crop.water_capacity_ml
        )
        world = step.world

        parts: dict[str, Json] = {
            "state": _state(world),
            "observations": [o.model_dump(mode="json") for o in step.observations],
            "ground_truth": truth.model_dump(mode="json"),
        }
        digests = " ".join(f"{name}={_digest(parts[name])}" for name in PARTS)
        days.append(f"day {day:02d}: {digests}")

        observations.extend(step.observations)
        truths.append(truth)

    return Baseline(days, _summary(world, observations, truths))


def _state(world: GreenhouseWorld) -> Json:
    """The hidden world, without the simple model's creation-time draws.

    Water stress is the one value from the model's own section included,
    because it changes every day and drives growth.
    """
    return {
        "simulated_day": world.simulated_day,
        "environment": world.environment.model_dump(mode="json"),
        "plants": [
            {
                "plant_id": plant.plant_id,
                "age_days": plant.age_days,
                "stem_length_cm": plant.stem_length_cm,
                "lowered_length_cm": plant.lowered_length_cm,
                "water_reservoir_ml": plant.water_reservoir_ml,
                "water_stress": world.plant_model.plants[plant.plant_id].water_stress,
                "cumulative_harvest_g": plant.cumulative_harvest_g,
                "trusses": [
                    {
                        "truss_id": truss.truss_id,
                        "index": truss.index,
                        "age_days": truss.age_days,
                        "stage": truss.stage.value,
                        "fruits": [
                            {
                                "fruit_id": fruit.fruit_id,
                                "age_days": fruit.age_days,
                                "diameter_mm": fruit.diameter_mm,
                                "mass_g": fruit.mass_g,
                                "ripeness_stage": fruit.ripeness_stage.value,
                                "status": fruit.status.value,
                            }
                            for fruit in truss.fruits
                        ],
                    }
                    for truss in plant.trusses
                ],
            }
            for plant in world.plants
        ],
    }


def _summary(
    world: GreenhouseWorld,
    observations: list[Observation],
    truths: list[GroundTruth],
) -> dict[str, Json]:
    """Where a run ended, in numbers a reviewer can read in a diff."""
    fruits = [fruit for plant in world.plants for truss in plant.trusses for fruit in truss.fruits]
    on_plants = [fruit for fruit in fruits if fruit.status != FruitStatus.HARVESTED]
    stems = [plant.stem_length_cm for plant in world.plants]
    values_by_type: dict[str, list[float]] = {}
    for observation in observations:
        values_by_type.setdefault(observation.observation_type.value, []).append(observation.value)
    accuracy = observation_accuracy(observations, truths)

    return {
        "plants": len(world.plants),
        "days": world.simulated_day,
        "air_temperature_c": round(world.environment.air_temperature_c, 3),
        "humidity_pct": round(world.environment.humidity_pct, 3),
        "stem_length_cm": {
            "min": round(min(stems), 2),
            "mean": round(fmean(stems), 2),
            "max": round(max(stems), 2),
        },
        "lowered_length_cm": round(sum(p.lowered_length_cm for p in world.plants), 2),
        "water_reservoir_ml_mean": round(fmean(p.water_reservoir_ml for p in world.plants), 2),
        "fully_water_stressed_plants": sum(
            state.water_stress == 1.0 for state in world.plant_model.plants.values()
        ),
        "trusses": sum(len(plant.trusses) for plant in world.plants),
        "fruits_by_status": _counts(fruit.status.value for fruit in fruits),
        "fruits_by_ripeness": _counts(fruit.ripeness_stage.value for fruit in fruits),
        "fruit_mass_on_plants_g": round(sum(fruit.mass_g for fruit in on_plants), 2),
        "cumulative_harvest_g": round(sum(p.cumulative_harvest_g for p in world.plants), 2),
        "observations_by_type": {k: len(v) for k, v in sorted(values_by_type.items())},
        "observation_value_sums": {k: round(sum(v), 1) for k, v in sorted(values_by_type.items())},
        "observation_mean_absolute_error": {
            entry.observation_type.value: round(entry.mean_absolute_error, 3)
            for entry in accuracy.by_type
        },
    }


def _counts(values: Iterable[str]) -> dict[str, Json]:
    return dict(sorted(Counter(values).items()))


def _digest(value: Json) -> str:
    canonical = json.dumps(_rounded(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _rounded(value: Json) -> Json:
    if isinstance(value, float):
        return round(value, DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _recorded() -> dict[str, dict[str, Json]]:
    recorded: dict[str, dict[str, Json]] = json.loads(FIXTURE.read_text())
    return recorded


def _first_divergence(actual: list[str], recorded: list[str]) -> str | None:
    for actual_day, recorded_day in zip(actual, recorded, strict=False):
        if actual_day == recorded_day:
            continue
        moved = [
            part.split("=")[0]
            for part, was in zip(actual_day.split()[2:], recorded_day.split()[2:], strict=True)
            if part != was
        ]
        return f"{actual_day.split(':')[0]} is the first to diverge, in: {', '.join(moved)}"
    if len(actual) != len(recorded):
        return f"the run lasted {len(actual)} days, not the recorded {len(recorded)}"
    return None


def test_every_registered_scenario_has_a_recorded_baseline() -> None:
    assert sorted(_recorded()) == SCENARIOS


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_a_reference_scenario_runs_day_by_day_as_recorded(scenario_id: str) -> None:
    recorded = _recorded()[scenario_id]["days"]
    assert isinstance(recorded, list)

    divergence = _first_divergence(_run(scenario_id).days, [str(day) for day in recorded])

    assert divergence is None, f"{scenario_id}: {divergence}"


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_a_reference_scenario_ends_where_recorded(scenario_id: str) -> None:
    assert _run(scenario_id).summary == _recorded()[scenario_id]["summary"]


def _update() -> None:
    recorded = {
        scenario_id: {"summary": _run(scenario_id).summary, "days": _run(scenario_id).days}
        for scenario_id in SCENARIOS
    }
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(recorded, indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_reference_baseline.py --update")
    _update()
    print(f"wrote {FIXTURE}")
