"""A run's capability and goal context (P15.2, decision 0061): what a
principal may read and do in an epoch of a scenario's run, built from its
installation as it plays, its scenario and its authorisation. It names
what the run's gateway acts on, and every source of what the run delivers,
at the cadence it delivers it."""

import re
from collections import defaultdict
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.context import ActionCadence, CropBasis, SourceKind
from greenhouse_protocol.contracts.gateway import GatewayLimits
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.plan import Principal, PrincipalKind

from greenhouse_sim.climate.control import Control, HeatingLoop, VentingLoop, VentStage
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import layout_names
from greenhouse_sim.sensors.air import samples
from greenhouse_sim.services.climate_runs import most_heating_c
from greenhouse_sim.services.crop_log import WALKED
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.gateway import (
    LOCAL_AUTHORISATION,
    LOCAL_OPERATOR,
    run_items,
    run_kinds,
)
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.policy_context import (
    CROP_WALK,
    HEAT_METER,
    OPENS,
    delivered_every_s,
    run_context,
)
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.identifiers import ITEM_ID_PATTERN
from greenhouse_sim.world.sensors import PointSensor

SCENARIO: Final = "reference_greenhouse"
LIMITS: Final = GatewayLimits(max_actions=10, max_occurrences=100)
EVERY_S: Final = 300.0
# Every record there is, in one batch.
ALL: Final = 10**6
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="policy")


@pytest.fixture(scope="module")
def plain() -> Iterator[Simulator]:
    with Simulator() as made:
        yield made


def _every_layout() -> list[tuple[str, str]]:
    return [
        (scenario_id, layout)
        for scenario_id in sorted(SCENARIO_REGISTRY)
        for layout in layout_names(scenario_id)
    ]


@pytest.mark.parametrize(("scenario_id", "layout"), _every_layout())
def test_a_policy_may_act_on_what_the_run_acts_on_and_as_it_does(
    plain: Simulator, scenario_id: str, layout: str
) -> None:
    played = changed(
        plain.catalogue, scenario(plain.catalogue, scenario_id), SceneChanges(layout=layout)
    )
    context = run_context(
        played,
        run_id="run",
        epoch=0,
        principal=LOCAL_OPERATOR,
        authorisation=LOCAL_AUTHORISATION,
        limits=LIMITS,
        every_s=EVERY_S,
    )

    assert context.items() == run_items(played)
    assert {cadence.kind for cadence in context.cadences} <= run_kinds(played)
    taken = registration(played).crop_actions
    assert all(
        crop.crop_actions == (frozenset() if taken is None else taken.kinds)
        for crop in context.crops
    )
    assert all(crop.grown_by == CropBasis.PLANT for crop in context.crops)


def test_the_reference_greenhouses_context_lists_its_installation(plain: Simulator) -> None:
    config = scenario(plain.catalogue, SCENARIO)
    context = run_context(
        config,
        run_id="run",
        epoch=0,
        principal=LOCAL_OPERATOR,
        authorisation=LOCAL_AUTHORISATION,
        limits=LIMITS,
        every_s=EVERY_S,
    )
    by_id = {source.source_id: source for source in context.sources}

    sensors = [source for source in context.sources if source.kind == SourceKind.SENSOR]
    assert len(sensors) == 13
    assert all(source.quantities[0].every_s == EVERY_S for source in sensors)
    assert by_id["co2"].quantities[0].observation_type == ObservationType.CO2_PPM
    assert [(q.observation_type, q.every_s) for q in by_id[HEAT_METER].quantities] == [
        (ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2, 3600.0)
    ]
    assert [q.observation_type for q in by_id[CROP_WALK].quantities] == list(WALKED)
    assert by_id[CROP_WALK].kind == SourceKind.MEASUREMENT
    devices = {device.device_id: device.does for device in context.devices}
    assert devices["heater"] == {"heats"}
    assert devices["dehumidifier"] == {"dries", "gives_off_heat"}
    assert devices["door"] == {OPENS}
    assert not any(device.auto for device in context.devices)
    assert [(t.target, t.unit, t.low, t.high) for t in context.targets] == [
        ("heating_day", "°C", 0.0, 40.0),
        ("heating_night", "°C", 0.0, 40.0),
    ]
    assert [(crop.scope_id, len(crop.plants)) for crop in context.crops] == [
        ("row_1", 8),
        ("row_2", 8),
        ("row_3", 8),
        ("row_4", 8),
    ]
    assert context.cadences[0] == ActionCadence(kind=ActionKind.SET_TARGET, every_s=60.0)
    assert set(context.cadences[1:]) == {
        ActionCadence(kind=kind, every_s=DAY_S, first_s=DAY_S)
        for kind in (
            ActionKind.HARVEST,
            ActionKind.LOWER,
            ActionKind.REMOVE_LEAF,
            ActionKind.INSPECT,
        )
    }
    assert context.grants == tuple(LOCAL_AUTHORISATION.grants_of(LOCAL_OPERATOR))
    assert context.goals == ()


def test_a_heating_target_goes_no_higher_than_the_dead_band_allows(plain: Simulator) -> None:
    box = SCENARIO_REGISTRY["climate_box"]
    control = Control(
        heating=HeatingLoop(actuator_id="heater", day_c=18.0, night_c=16.0),
        venting=VentingLoop(
            vents=["roof_vent", "side_vent"],
            day_c=22.0,
            night_c=20.0,
            band_c=1.0,
            stages=[VentStage(above_c=0.0, level=0.2), VentStage(above_c=1.5, level=1.0)],
        ),
    )
    config = box.model_copy(update={"control": control})

    context = run_context(
        config,
        run_id="run",
        epoch=0,
        principal=LOCAL_OPERATOR,
        authorisation=LOCAL_AUTHORISATION,
        limits=LIMITS,
        every_s=EVERY_S,
    )

    assert [(t.target, t.high) for t in context.targets] == [
        ("heating_day", most_heating_c(config, "heating_day")),
        ("heating_night", most_heating_c(config, "heating_night")),
    ]
    assert context.targets[0].high == 19.5


@pytest.mark.parametrize(
    ("cadence_s", "every_s", "delivered_s"),
    [
        (60.0, 300.0, 300.0),
        (300.0, 60.0, 300.0),
        (7.0, 300.0, 2100.0),
        (1.5, 2.0, 6.0),
        (1.2, 300.0, 300.0),
        (2.5, 300.0, 300.0),
    ],
)
def test_a_sensor_reaches_a_consumer_at_the_least_common_multiple(
    cadence_s: float, every_s: float, delivered_s: float
) -> None:
    """As the sampling delivers it: every sample a sensor takes at a
    multiple of the consumer's cadence, its moments worked out as a run
    works them out (`sensors.air.samples`)."""
    sensor = PointSensor(
        sensor_id="s",
        kind=SensorKind.TEMPERATURE,
        position=Vector3(x=0.0, y=0.0, z=1.0),
        cadence_s=cadence_s,
    )
    delivered = [moment for moment in samples(sensor, DAY_S) if moment % every_s == 0]

    assert delivered_every_s(cadence_s, every_s) == delivered_s
    assert {later - earlier for earlier, later in pairwise(delivered)} == {delivered_s}


def test_a_source_that_names_no_sensor_is_named_as_no_sensor_is(plain: Simulator) -> None:
    config = scenario(plain.catalogue, SCENARIO)
    first, *others = config.layout.sensors
    renamed = [first.model_copy(update={"sensor_id": "heat_meter"}), *others]
    sensed = config.model_copy(
        update={"layout": config.layout.model_copy(update={"sensors": renamed})}
    )

    context = run_context(
        sensed,
        run_id="run",
        epoch=0,
        principal=LOCAL_OPERATOR,
        authorisation=LOCAL_AUTHORISATION,
        limits=LIMITS,
        every_s=EVERY_S,
    )

    ids = [source.source_id for source in context.sources]
    assert {"heat_meter", HEAT_METER, CROP_WALK} <= set(ids)
    assert not any(re.fullmatch(ITEM_ID_PATTERN, name) for name in (HEAT_METER, CROP_WALK))


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    "scenario_id",
    ["climate_box", pytest.param(SCENARIO, marks=pytest.mark.slow)],
)
def test_every_reading_a_day_delivers_is_of_a_source_its_context_lists(
    simulator: Simulator, scenario_id: str
) -> None:
    clock = _Clock()
    played = Playback(simulator, scenario_id, seconds_per_day=24.0, clock=clock)
    context = played.context(POLICY)
    assert played.work_day(0)
    played.command(PlaybackCommand.PLAY)
    clock.now = 24.0
    readings = played.records_after(0, ALL).records
    by_id = {source.source_id: source for source in context.sources}
    unnamed = {
        quantity.observation_type: quantity.every_s
        for source_id in (HEAT_METER, CROP_WALK)
        for quantity in by_id[source_id].quantities
    }

    assert readings
    taken: dict[tuple[str, ObservationType], list[float]] = defaultdict(list)
    periods: dict[tuple[str, ObservationType], float] = {}
    for reading in readings:
        if reading.sensor_id is None:
            every_s = unnamed[reading.observation_type]
        else:
            (quantity,) = by_id[reading.sensor_id].quantities
            assert quantity.observation_type == reading.observation_type
            every_s = quantity.every_s
        assert every_s is not None
        # Each at a multiple of its source's period, the walk at noon.
        since_s = (reading.timestamp - played.start).total_seconds()
        phase_s = DAY_S / 2 if reading.observation_type in WALKED else 0.0
        assert since_s % every_s == phase_s, reading
        source = (reading.sensor_id or reading.plant_id or "", reading.observation_type)
        taken[source].append(since_s)
        periods[source] = every_s
    # And as often as the context says, not only on its moments.
    for source, moments in taken.items():
        steps = {later - earlier for earlier, later in pairwise(sorted(set(moments)))}
        assert not steps or min(steps) == periods[source], source
    assert {r.observation_type for r in readings} == context.observed_types()


def test_a_playback_gives_the_context_of_its_epoch_and_authorisation(
    simulator: Simulator, tmp_path: Path
) -> None:
    played = Playback(
        simulator, SCENARIO, seconds_per_day=24.0, clock=_Clock(), epochs=Epochs(tmp_path)
    )
    state = played.state()

    context = played.context(LOCAL_OPERATOR)

    assert (context.run_id, context.epoch, context.greenhouse_id) == (
        state.run_id,
        state.epoch,
        state.greenhouse_id,
    )
    assert context.grants == tuple(LOCAL_AUTHORISATION.grants_of(LOCAL_OPERATOR))
    assert played.context(POLICY).grants == ()
    policies = AuthorisationConfig(
        version=2,
        groups=(
            AuthorisationGroup(
                group_id="policies",
                principals=frozenset({POLICY}),
                grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
            ),
        ),
    )
    played.authorise(policies)
    assert played.context(POLICY).grants == policies.groups[0].grants
    played.command(PlaybackCommand.RESTART)
    assert played.context(POLICY).epoch == state.epoch + 1
