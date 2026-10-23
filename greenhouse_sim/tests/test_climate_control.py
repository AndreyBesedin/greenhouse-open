"""A greenhouse's climate controller as data (P11.1): its loops, each with
its targets and band, its vents in stages, checked so that heating and
venting keep a dead band between them, every loop reads what another runs,
and its day and night fall on the minute; its heating loop the thermostat a
run follows; and a scenario's control running its own devices, its heating
loop alone until the house decides every loop (P11.2)."""

from typing import Any, Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.climate.control import (
    CirculationLoop,
    Control,
    DehumidifyingLoop,
    HeatingLoop,
    VentingLoop,
    VentStage,
)
from greenhouse_sim.climate.thermostat import Thermostat
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.units import HOUR_S

REFERENCE: Final = SCENARIO_REGISTRY["reference_greenhouse"]
HEATING: Final = HeatingLoop(actuator_id="heater", day_c=18.0, night_c=16.0)
# Its first stage closes 1.5 °C above where the heater switches off, by
# day (21 - 1 - 18.5) and by night (19 - 1 - 16.5): a dead band of 1 °C kept.
VENTING: Final = VentingLoop(
    vents=["roof_vent_1", "roof_vent_2"],
    day_c=21.0,
    night_c=19.0,
    stages=[VentStage(above_c=0.0, level=0.5), VentStage(above_c=2.0, level=1.0)],
)
DEHUMIDIFYING: Final = DehumidifyingLoop(actuator_id="dehumidifier", target_pct=85.0)


def _control(**loops: Any) -> Control:
    return Control.model_validate({"heating": HEATING.model_dump()} | loops)


def test_its_heating_loop_is_the_thermostat_a_run_follows() -> None:
    control = Control(heating=HEATING, day_from_s=6 * HOUR_S, night_from_s=20 * HOUR_S)

    assert control.thermostat() == Thermostat(
        actuator_id="heater",
        day_c=18.0,
        night_c=16.0,
        day_from_s=6 * HOUR_S,
        night_from_s=20 * HOUR_S,
        band_c=1.0,
    )
    assert Control(venting=VENTING).thermostat() is None
    # The reference greenhouse's, decision 0042's thermostat as it was.
    assert REFERENCE.thermostat == Thermostat(actuator_id="heater", day_c=18.0, night_c=16.0)


def test_it_runs_a_loop_at_least_its_day_before_its_night_on_the_minute() -> None:
    with pytest.raises(ValidationError, match="runs one loop at least"):
        Control()
    with pytest.raises(ValidationError, match="day starts before its night"):
        Control(heating=HEATING, day_from_s=20 * HOUR_S, night_from_s=6 * HOUR_S)
    with pytest.raises(ValidationError, match="start on the minute"):
        Control(heating=HEATING, day_from_s=7 * HOUR_S + 30.0)


def test_its_vents_open_in_stages_each_further_at_a_higher_temperature() -> None:
    stage = VentStage(above_c=1.0, level=0.5)
    for stages in (
        [stage, stage],
        [stage, VentStage(above_c=2.0, level=0.5)],
        [stage, VentStage(above_c=0.5, level=1.0)],
    ):
        with pytest.raises(ValidationError, match="open further, each at a higher temperature"):
            VENTING.model_validate(VENTING.model_dump() | {"stages": stages})
    with pytest.raises(ValidationError, match="each of its vents once"):
        VENTING.model_validate(VENTING.model_dump() | {"vents": ["roof_vent_1"] * 2})
    for level in (0.0, 1.5):
        with pytest.raises(ValidationError, match="level"):
            VentStage(above_c=0.0, level=level)


@pytest.mark.parametrize(
    ("period", "venting"), [("day", {"day_c": 20.25}), ("night", {"night_c": 18.25})]
)
def test_heating_and_venting_keep_their_dead_band_by_day_and_by_night(
    period: str, venting: dict[str, float]
) -> None:
    # The first stage closes at the setpoint less the band, 1 °C, here 0.75
    # °C above where the heater switches off, its setpoint and half its band.
    narrow = VENTING.model_copy(update=venting).model_dump()
    with pytest.raises(ValidationError, match=f"by {period}, the vents' first stage closes 0.75"):
        _control(venting=narrow)

    assert _control(venting=VENTING.model_dump(), dead_band_c=1.5).venting == VENTING
    with pytest.raises(ValidationError, match=r"within the dead band of 1\.75"):
        _control(venting=VENTING.model_dump(), dead_band_c=1.75)


def test_a_loop_reads_what_another_runs() -> None:
    fans = CirculationLoop(fans=["fan_left", "fan_right"], from_stage=2)
    with pytest.raises(ValidationError, match="follows the vents: a venting loop runs them"):
        _control(circulation=fans.model_dump())
    with pytest.raises(ValidationError, match="from stage 3, and they have 2"):
        _control(venting=VENTING.model_dump(), circulation=fans.model_dump() | {"from_stage": 3})
    with pytest.raises(ValidationError, match="opens the vents' first stage"):
        _control(dehumidifying=DEHUMIDIFYING.model_dump())
    alone = DEHUMIDIFYING.model_copy(update={"vents_when_drier": False})
    assert _control(dehumidifying=alone.model_dump()).dehumidifying == alone
    with pytest.raises(ValidationError, match="each of its fans once"):
        CirculationLoop(fans=["fan_left", "fan_left"])


def test_dehumidifying_keeps_its_band_short_of_saturation_and_vents_only_into_drier_air() -> None:
    for target, band in ((98.0, 5.0), (2.0, 5.0)):
        with pytest.raises(ValidationError, match="between dry air and saturation"):
            DehumidifyingLoop(actuator_id="dehumidifier", target_pct=target, band_pct=band)
    with pytest.raises(ValidationError, match="its band is narrower than its margin"):
        DehumidifyingLoop(
            actuator_id="dehumidifier", target_pct=85.0, drier_by_g_kg=0.5, drier_band_g_kg=0.5
        )


def test_it_says_every_device_its_loops_run() -> None:
    control = _control(
        venting=VENTING.model_dump(),
        circulation={"fans": ["fan_left"]},
        dehumidifying=DEHUMIDIFYING.model_dump(),
    )

    assert control.loops() == ["heating", "venting", "circulation", "dehumidifying"]
    assert control.runs() == ["heater", "roof_vent_1", "roof_vent_2", "fan_left", "dehumidifier"]


def _reference(**control: Any) -> ScenarioConfig:
    return ScenarioConfig.model_validate(
        REFERENCE.model_dump()
        | {"daily": [], "control": {"heating": HEATING.model_dump()} | control}
    )


@pytest.mark.parametrize(
    ("control", "refused"),
    [
        (
            {"heating": HEATING.model_dump() | {"actuator_id": "dehumidifier"}},
            "heating loop runs one of its heaters, not 'dehumidifier'",
        ),
        (
            {
                "dehumidifying": DEHUMIDIFYING.model_dump() | {"actuator_id": "heater"},
                "venting": VENTING.model_dump(),
            },
            "dehumidifying loop runs one of its dehumidifiers, not 'heater'",
        ),
        (
            {"venting": VENTING.model_dump(), "circulation": {"fans": ["heater"]}},
            "circulation loop runs one of its fans, not 'heater'",
        ),
        (
            {"venting": VENTING.model_dump() | {"vents": ["door"]}},
            "a venting loop runs its vents, not 'door'",
        ),
    ],
)
def test_a_scenarios_control_runs_its_own_devices_of_their_kinds(
    control: dict[str, Any], refused: str
) -> None:
    with pytest.raises(ValidationError, match=refused):
        _reference(**control)


def test_a_scenarios_control_takes_no_daily_commands_to_what_it_runs() -> None:
    with pytest.raises(ValidationError, match="its control runs heater: daily commands to it"):
        ScenarioConfig.model_validate(
            REFERENCE.model_dump()
            | {"daily": [{"time_of_day_s": 0.0, "actuator_id": "heater", "level": 1.0}]}
        )
    # Its own daily commands open and shut its roof vents.
    with pytest.raises(
        ValidationError, match="runs roof_vent_1, roof_vent_2: daily commands to them would take"
    ):
        ScenarioConfig.model_validate(
            REFERENCE.model_dump()
            | {"control": {"heating": HEATING.model_dump(), "venting": VENTING.model_dump()}}
        )


def test_a_scenarios_control_runs_its_heating_loop_alone_until_the_house_decides_every_loop() -> (
    None
):
    with pytest.raises(
        ValidationError,
        match=r"until the house decides every loop \(P11.2\), not its venting, circulation",
    ):
        _reference(venting=VENTING.model_dump(), circulation={"fans": ["fan_left", "fan_right"]})
    assert _reference().thermostat == REFERENCE.thermostat
