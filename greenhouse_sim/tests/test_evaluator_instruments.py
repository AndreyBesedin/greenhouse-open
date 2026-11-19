"""The evaluator's instruments (P25.2, decision 0082), read from the run an
episode carried out once its policy stopped: the heat given, over whole
hours the sum of the heat records the policy was given; the heating loop's
switches, those the house's air states give, to the moment; a command
taking the heater over, as that command's switch; the steered air, not the
scenario's own; each measure's source given as its series; and the
harvest, as the run's harvest events."""

import sys
from bisect import bisect_left
from collections.abc import Iterator
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.benchmark import (
    FromInstrument,
    Instrument,
    packaged_measure,
    packaged_measures,
)
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity, Revise
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.measuring import series_value
from greenhouse_protocol.plan import Asap, PlannedAction, Principal, PrincipalKind

from greenhouse_sim.climate.thermostat import ON
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.evaluation.instruments import Instruments, Picked, SetBy, harvest
from greenhouse_sim.experiment import Episode, EpisodeCarriedOut, carry_out_episode
from greenhouse_sim.scenarios.crop_parameters import SimpleCrop
from greenhouse_sim.services.climate_readings import house_air_at
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of, tended_box

SCENARIO: Final = "reference_greenhouse"
OWN: Final = RunRequest(SCENARIO)
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="heater-off")
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
# The policy turns the heater off at its second decision, six hours in, and
# its episode ends six hours later; the night is held at 16 °C till then,
# the calm 10 °C outside cooling the house once the heater is off.
DECIDES_EVERY_S: Final = 6 * HOUR_S
OFF_AT_S: Final = 6 * HOUR_S
END_S: Final = 12 * HOUR_S
HEATER: Final = "heater"
HEATER_W: Final = 30_000.0
OUTSIDE_C: Final = 10.0
# The house's floor, 12 m by 9.6 m.
FLOOR_M2: Final = 115.2
# A heat record is kept to a kilojoule per m²: half of one either way.
RECORD_ROUNDING_MJ_M2: Final = 0.0005
# How far either side of a switch the controller's level is read.
AROUND_S: Final = 1e-6


class _HeaterOff:
    """Keeps its plan, but at its second decision turns the heater off."""

    identity: Final = PolicyIdentity(name="heater-off", version="1")
    decide_every_s: Final = DECIDES_EVERY_S

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._decided = 0

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self._decided += 1
        if self._decided != 2:
            return Keep()
        off = SetLevel(device_id=HEATER, level=0.0)
        return Revise(
            actions=(PlannedAction(action_id="off", action=off, timing=Asap(), proposed_by=POLICY),)
        )

    def stop(self) -> None: ...


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    house = cut(SCENARIO, days=1, plants=(1, 1), sensors=("temperature_front",))
    with simulator_of(house, authorisation=AUTHORISATION) as made:
        yield made


@pytest.fixture(scope="module")
def steered(simulator: Simulator) -> tuple[EpisodeCarriedOut, list[Delivery]]:
    deliveries: list[Delivery] = []
    episode = Episode(scenario_id=SCENARIO, policy=_HeaterOff(), principal=POLICY, end_s=END_S)
    return carry_out_episode(simulator, episode, kept=deliveries.append), deliveries


def _held_before(states: tuple[object, ...], moments: list[float], time_s: float) -> float:
    """The level a device's states held just before `time_s`."""
    state = states[bisect_left(moments, time_s) - 1]
    assert hasattr(state, "level")
    return float(state.level)


def test_the_heat_given_over_each_whole_hour_is_the_heat_record_its_policy_was_given(
    simulator: Simulator, steered: tuple[EpisodeCarriedOut, list[Delivery]]
) -> None:
    carried, deliveries = steered
    start = run_start(simulator.catalogue, SCENARIO)
    records = {
        (record.timestamp - start).total_seconds(): record.value
        for delivered in deliveries
        for record in delivered.observations
        if record.observation_type == ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2
    }
    instruments = Instruments(simulator, carried.run, END_S)
    heat = instruments.series(FromInstrument(instrument=Instrument.HEAT_GIVEN, quantity="heat"))
    given = packaged_measure("heat-given", 1)

    floor = instruments.floor_m2

    def over(from_s: float, until_s: float) -> float:
        return series_value(given, heat[None], [(from_s, until_s)], floor_area_m2=floor)

    assert floor == pytest.approx(FLOOR_M2)
    # An hour's record at its end, the last given at the episode's.
    assert sorted(records) == [hour * HOUR_S for hour in range(1, 13)]
    for end_s, value in records.items():
        assert over(end_s - HOUR_S, end_s) == pytest.approx(value, abs=RECORD_ROUNDING_MJ_M2)
        exact = instruments.heat_given_j(end_s - HOUR_S, end_s) / 1e6 / floor
        assert over(end_s - HOUR_S, end_s) == pytest.approx(exact, rel=1e-12)
    # The heater on from the start, as the night needs, and off from six hours.
    assert over(0.0, HOUR_S) > 0
    assert over(OFF_AT_S, END_S) == 0.0
    assert over(0.0, END_S) == pytest.approx(
        sum(records.values()), abs=len(records) * RECORD_ROUNDING_MJ_M2
    )


def test_the_heating_loops_switches_are_those_its_house_air_states_give(
    simulator: Simulator,
) -> None:
    """At every minute the house's air says whether its heating loop ran
    the heater up to then; the heater's states say it to the moment, more
    often than the minutes do."""
    instruments = Instruments(simulator, OWN, DAY_S)
    house = climate_run(simulator, OWN)[1].house
    heater = instruments.equipment[HEATER]
    moments = [state.at_s for state in heater]

    assert {state.set_by for state in heater} == {SetBy.LOOP}
    flips = 0
    for minute in range(1, int(DAY_S // 60) + 1):
        heating = house.air_at(minute * 60.0).heating
        assert _held_before(heater, moments, minute * 60.0) == (ON if heating else 0.0)
        flips += heating != house.air_at((minute - 1) * 60.0).heating
    assert len(heater) - 1 > flips > 0
    # Each switch at the moment the controller's level changes.
    for before, state in pairwise(heater):
        assert house.controlled_at(state.at_s - AROUND_S)[HEATER] == before.level
        assert house.controlled_at(state.at_s + AROUND_S)[HEATER] == state.level != before.level


def test_a_command_that_takes_the_heater_over_shows_as_that_commands_switch(
    simulator: Simulator, steered: tuple[EpisodeCarriedOut, list[Delivery]]
) -> None:
    carried, _ = steered
    heater = Instruments(simulator, carried.run, END_S).equipment[HEATER]
    *looped, taken = heater

    assert [outcome.action for outcome in carried.record.outcomes] == [
        SetLevel(device_id=HEATER, level=0.0)
    ]
    assert (taken.at_s, taken.level, taken.set_by) == (OFF_AT_S, 0.0, SetBy.COMMAND)
    assert looped and {state.set_by for state in looped} == {SetBy.LOOP}
    assert all(state.at_s < OFF_AT_S for state in looped)


def test_on_a_steered_run_the_instruments_read_the_steered_air(
    simulator: Simulator, steered: tuple[EpisodeCarriedOut, list[Delivery]]
) -> None:
    """The run the episode carried out is the scenario's run with the plan
    its policy left: the same air until the heater is off, colder after."""
    carried, _ = steered
    by_hand = RunRequest(SCENARIO, plan=RunPlan.requested(commands=((OFF_AT_S, HEATER, 0.0),)))
    steered_air = Instruments(simulator, carried.run, END_S).house_air
    own_air = Instruments(simulator, OWN, END_S).house_air
    hourly = range(0, len(steered_air.times_s), 60)

    assert carried.run.plan.commanded() == ((OFF_AT_S, HEATER, 0.0),)
    for index in hourly:
        moment = steered_air.times_s[index]
        by_hand_c = house_air_at(simulator, by_hand, moment).temperature_c
        assert steered_air.temperature_c[index] == by_hand_c
        if moment <= OFF_AT_S:
            assert steered_air.temperature_c[index] == own_air.temperature_c[index]
    assert steered_air.temperature_c[-1] == pytest.approx(OUTSIDE_C, abs=0.01)
    assert min(own_air.temperature_c[len(own_air.times_s) // 2 :]) > OUTSIDE_C + 5
    steered_after = steered_air.heated_j[-1] - steered_air.heated_j[360]
    assert steered_air.times_s[360] == OFF_AT_S
    assert steered_after == 0.0 < own_air.heated_j[-1] - own_air.heated_j[360]


def test_each_instrument_measure_packaged_is_given_its_series(simulator: Simulator) -> None:
    """Every packaged measure an instrument feeds is given its series, and
    the heater's hours run at its power are the heat it gave."""
    instruments = Instruments(simulator, OWN, DAY_S)
    sources = {
        measure.source
        for measure in packaged_measures()
        if isinstance(measure.source, FromInstrument)
    }

    for source in sources:
        assert instruments.series(source)
    levels = instruments.series(
        FromInstrument(instrument=Instrument.EQUIPMENT_STATES, quantity="level")
    )[HEATER]
    day = [(0.0, DAY_S)]
    level_hours = series_value(packaged_measure("device-level-hours", 1), levels, day)
    switches = series_value(packaged_measure("device-switches", 1), levels, day)
    assert level_hours * HOUR_S * HEATER_W == pytest.approx(instruments.heat_given_j(0.0, DAY_S))
    assert switches == len(levels) - 1
    air = instruments.series(
        FromInstrument(instrument=Instrument.HOUSE_AIR, quantity="temperature")
    )
    assert air[None][:2] == [(0.0, 14.0), (60.0, instruments.house_air.temperature_c[1])]
    with pytest.raises(ValueError, match="gives no 'leaf_temperature'"):
        instruments.series(
            FromInstrument(instrument=Instrument.HOUSE_AIR, quantity="leaf_temperature")
        )
    with pytest.raises(InvalidRequest):
        Instruments(simulator, OWN, 2 * DAY_S)
    with pytest.raises(ValueError, match="the episode lasts from 0 to"):
        instruments.heat_given_j(0.0, 2 * DAY_S)


def test_the_harvest_is_the_runs_harvest_events() -> None:
    """A box whose fruit ripens within days, a round harvesting every third:
    its sixth day's round, as its events give it, and the measure of it the
    fruit's mass per m² of floor; the day the run ends on is none of it."""
    box = cut(
        "climate_box",
        days=9,
        season=True,
        crop=SimpleCrop(truss_interval_days=2, ripening_days_bounds=(3, 4)),
        crop_work=CropWork(harvest_every_days=3),
    )
    run = RunRequest("climate_box")
    with simulator_of(box) as ripening:
        start = run_start(ripening.catalogue, "climate_box")
        events = crop_records(ripening, run, 6, start, "climate_box")[1]
        instruments = Instruments(ripening, run, 9 * DAY_S)
        picked = instruments.harvest
        mass = instruments.series(
            FromInstrument(instrument=Instrument.HARVEST, quantity="fresh_mass")
        )

    assert events and picked == tuple(
        Picked(
            6 * DAY_S,
            event.plant_id or "",
            event.parameters["harvested_fruit_count"],
            event.parameters["harvested_mass_g"],
        )
        for event in events
    )
    floor = instruments.floor_m2
    assert series_value(
        packaged_measure("harvest", 1), mass[None], [(0.0, 9 * DAY_S)], floor_area_m2=floor
    ) == pytest.approx(sum(each.fresh_mass_g for each in picked) / floor)


def test_a_plans_harvest_done_is_picked_at_its_days_start() -> None:
    """The organ crop's first days ripen no fruit: a harvest on its second
    picks none, and says so."""
    box = tended_box("tended_box", 2)
    (plant_id,) = plant_ids(box)
    run = RunRequest(
        "tended_box", plan=RunPlan.requested(crop=((DAY_S, plant_id, "harvest_ripe", ""),))
    )
    with simulator_of(box) as tended:
        picked = harvest(tended, run, 2 * DAY_S)

    assert picked == (Picked(DAY_S, plant_id, 0, 0.0),)
