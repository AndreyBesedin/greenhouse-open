"""What a run's crop delivers as records (P10.4): its harvests as events and
a daily walk through it as observations, from the same crop the viewer
draws, of either crop model (P14.3)."""

from datetime import timedelta

import pytest
from greenhouse_protocol.contracts.conformance import check_events, check_observations
from greenhouse_protocol.enums import EventType, ObservationType

from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.core.simple_crop import SimplePlant
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.crop_parameters import CropWalk, SimpleCrop
from greenhouse_sim.services import checkpoints, crop
from greenhouse_sim.services.crop_log import WALK_S, crop_records
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator

SCENARIO = "reference_greenhouse"
# The reference run's first harvest round with red fruit to pick: the
# weekly round after its opening day, 86.
FIRST_ROUND = 91
WALKED = {
    ObservationType.VISIBLE_FRUIT_COUNT,
    ObservationType.RIPE_FRUIT_COUNT,
    ObservationType.ESTIMATED_RIPE_MASS_G,
    ObservationType.VISIBLE_HEIGHT_CM,
}


def test_a_day_s_walk_records_every_plant_at_noon_with_the_run_s_identity(
    simulator: Simulator,
) -> None:
    start = run_start(PACKAGED, SCENARIO)
    _, run_id = air_through_a_run(simulator, RunRequest(SCENARIO))

    walked, harvests = crop_records(simulator, RunRequest(SCENARIO), 1, start, run_id)

    assert harvests == []  # no harvest round starts day 1
    assert len(walked) == 32 * len(WALKED)
    assert {o.observation_type for o in walked} == WALKED
    assert {o.timestamp for o in walked} == {start + timedelta(seconds=DAY_S + WALK_S)}
    assert {o.source.source_id for o in walked} == {run_id}
    assert check_observations(walked) == []
    # The same walk again is the same: its errors are drawn from the seed.
    assert crop_records(simulator, RunRequest(SCENARIO), 1, start, run_id)[0] == walked
    # Transplants a day on: no fruit yet, some height. A walk can miss a
    # fruit or count one twice, but counts none where there is none.
    heights = [o.value for o in walked if o.observation_type == ObservationType.VISIBLE_HEIGHT_CM]
    assert all(isinstance(h, float) and h > 0 for h in heights)
    counted = {ObservationType.VISIBLE_FRUIT_COUNT, ObservationType.RIPE_FRUIT_COUNT}
    assert {o.value for o in walked if o.observation_type in counted} == {0.0}


def _simple(plant: SimplePlant) -> dict[ObservationType, float]:
    """A plant of the simple crop as a walk without errors measures it."""
    on_it = [f for truss in plant.plant.trusses for f in truss.fruits if f.status != "HARVESTED"]
    ripe = [fruit for fruit in on_it if fruit.status == "RIPE"]
    return {
        ObservationType.VISIBLE_FRUIT_COUNT: float(len(on_it)),
        ObservationType.RIPE_FRUIT_COUNT: float(len(ripe)),
        ObservationType.ESTIMATED_RIPE_MASS_G: round(sum(fruit.mass_g for fruit in ripe), 1),
        ObservationType.VISIBLE_HEIGHT_CM: round(plant.standing_cm(), 1),
    }


def test_a_day_s_walk_through_the_simple_crop_records_each_plant_as_it_stands(
    simulator: Simulator,
) -> None:
    """As the engine's sensors measure it: its fruits not harvested, its
    ripe ones and their mass, its standing stem; with the walk's errors."""
    run = RunRequest("climate_box")
    start = run_start(PACKAGED, "climate_box")
    _, run_id = air_through_a_run(simulator, run)

    walked, harvests = crop_records(simulator, run, 3, start, run_id)

    assert harvests == []
    assert len(walked) == 32 * len(WALKED)
    assert {o.timestamp for o in walked} == {start + timedelta(seconds=3 * DAY_S + WALK_S)}
    assert {o.source.source_id for o in walked} == {run_id}
    assert check_observations(walked) == []
    grown = crop.scenario_crop(simulator, run)
    assert not crop.is_organ(grown)
    plants = grown.plants_on(3)
    heights = {
        o.plant_id: o.value
        for o in walked
        if o.observation_type == ObservationType.VISIBLE_HEIGHT_CM
    }
    assert heights.keys() == {plant.plant_id for plant in plants}
    assert heights != {p.plant_id: _simple(p)[ObservationType.VISIBLE_HEIGHT_CM] for p in plants}
    # Without the walk's errors, what it records is the plant as it stands.
    config = SCENARIO_REGISTRY["climate_box"]
    exact = config.model_copy(
        update={
            "crop_walk": CropWalk(
                fruit_count_noise_probability=0.0, ripe_mass_noise_pct=0.0, height_noise_cm=0.0
            )
        }
    )
    with Simulator(Catalogue(PACKAGED.with_config(exact))) as without_errors:
        _, exact_id = air_through_a_run(without_errors, run)
        recorded, _ = crop_records(without_errors, run, 3, start, exact_id)
    assert {(o.plant_id, o.observation_type): o.value for o in recorded} == {
        (plant.plant_id, kind): value for plant in plants for kind, value in _simple(plant).items()
    }


def test_the_simple_crop_s_harvest_round_is_an_event_per_plant_picked(
    simulator: Simulator,
) -> None:
    """A climate box whose fruit ripens within days, and which a round
    harvests every third: each event is the fruit its plant's round
    harvested, and the mass it added to its harvest."""
    config = SCENARIO_REGISTRY["climate_box"].model_copy(
        update={
            "crop": SimpleCrop(truss_interval_days=2, ripening_days_bounds=(3, 4)),
            "crop_work": CropWork(harvest_every_days=3),
            "duration_days": 9,
        }
    )
    run = RunRequest("climate_box")
    start = run_start(PACKAGED, "climate_box")
    with Simulator(Catalogue(PACKAGED.with_config(config))) as ripening:
        _, run_id = air_through_a_run(ripening, run)
        grown = crop.scenario_crop(ripening, run)
        rounds = {day: crop_records(ripening, run, day, start, run_id)[1] for day in range(10)}
        plants = {day: {p.plant_id: p for p in grown.plants_on(day)} for day in range(10)}

    assert [day for day, harvests in rounds.items() if harvests] == [6, 9]
    for day in (6, 9):
        assert check_events(rounds[day]) == []
        for event in rounds[day]:
            plant = plants[day][event.plant_id or ""]
            before = plants[day - 1][plant.plant_id]
            assert isinstance(plant, SimplePlant) and isinstance(before, SimplePlant)
            assert event.event_type == EventType.HARVEST
            assert event.timestamp == start + timedelta(seconds=day * DAY_S)
            added = plant.plant.cumulative_harvest_g - before.plant.cumulative_harvest_g
            assert event.parameters["harvested_mass_g"] == round(added, 1) > 0
            assert event.parameters["harvested_fruit_count"] > 0


@pytest.mark.slow
def test_a_harvest_round_is_an_event_per_plant_picked_as_the_plant_s_history_has_it(
    simulator: Simulator,
) -> None:
    # From the kept opening day, 86, the first with red fruit, as the viewer
    # opens the run; the round after it starts day 91.
    assert checkpoints.load_openings(simulator) == []
    start = run_start(PACKAGED, SCENARIO)
    _, run_id = air_through_a_run(simulator, RunRequest(SCENARIO))

    walked, harvests = crop_records(simulator, RunRequest(SCENARIO), FIRST_ROUND, start, run_id)

    assert harvests, "the first round after the opening day picks red fruit"
    assert check_events(harvests) == []
    assert {e.event_type for e in harvests} == {EventType.HARVEST}
    assert {e.timestamp for e in harvests} == {start + timedelta(seconds=FIRST_ROUND * DAY_S)}
    # Each event is what the round picked from its plant, by its history.
    run = crop.run_crop(simulator, RunRequest(SCENARIO))
    before = {p.plant_id: p for p in run.plants_on(FIRST_ROUND - 1)}
    for event in harvests:
        plant = next(p for p in run.plants_on(FIRST_ROUND) if p.plant_id == event.plant_id)
        picked = [
            e
            for e in plant.history[len(before[plant.plant_id].history) :]
            if e.applied and isinstance(e.action, HarvestFruit)
        ]
        assert event.parameters == {
            "harvested_mass_g": round(sum(e.harvested_g for e in picked), 1),
            "harvested_fruit_count": len(picked),
        }
        assert event.parameters["harvested_mass_g"] > 0
    assert len(walked) == 32 * len(WALKED)
