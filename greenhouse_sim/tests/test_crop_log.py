"""What a run's organ-level crop delivers as records (P10.4): its harvests as
events and a daily walk through it as observations, from the same crop the
viewer draws."""

from datetime import timedelta

import pytest
from greenhouse_protocol.contracts.conformance import check_events, check_observations
from greenhouse_protocol.enums import EventType, ObservationType

from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import checkpoints, crop
from greenhouse_sim.services.crop_log import WALK_S, crop_records
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.sensors import run_start

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


def test_a_day_s_walk_records_every_plant_at_noon_with_the_run_s_identity() -> None:
    start = run_start(SCENARIO)
    _, run_id = air_through_a_run(SCENARIO)

    walked, harvests = crop_records(SCENARIO, 1, start, run_id)

    assert harvests == []  # no harvest round starts day 1
    assert len(walked) == 32 * len(WALKED)
    assert {o.observation_type for o in walked} == WALKED
    assert {o.timestamp for o in walked} == {start + timedelta(seconds=DAY_S + WALK_S)}
    assert {o.source.source_id for o in walked} == {run_id}
    assert check_observations(walked) == []
    # The same walk again is the same: its errors are drawn from the seed.
    assert crop_records(SCENARIO, 1, start, run_id)[0] == walked
    # Transplants a day on: no fruit yet, some height.
    heights = [o.value for o in walked if o.observation_type == ObservationType.VISIBLE_HEIGHT_CM]
    assert all(isinstance(h, float) and h > 0 for h in heights)


def test_a_scenario_with_the_simple_crop_has_no_records_of_it() -> None:
    _, run_id = air_through_a_run("climate_box")
    assert crop_records("climate_box", 1, run_start("climate_box"), run_id) == ([], [])


@pytest.mark.slow
def test_a_harvest_round_is_an_event_per_plant_picked_as_the_plant_s_history_has_it() -> None:
    # From the kept opening day, 86, the first with red fruit, as the viewer
    # opens the run; the round after it starts day 91.
    assert checkpoints.load_openings() == []
    start = run_start(SCENARIO)
    _, run_id = air_through_a_run(SCENARIO)

    walked, harvests = crop_records(SCENARIO, FIRST_ROUND, start, run_id)

    assert harvests, "the first round after the opening day picks red fruit"
    assert check_events(harvests) == []
    assert {e.event_type for e in harvests} == {EventType.HARVEST}
    assert {e.timestamp for e in harvests} == {start + timedelta(seconds=FIRST_ROUND * DAY_S)}
    # Each event is what the round picked from its plant, by its history.
    run = crop.run_crop(SCENARIO)
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
