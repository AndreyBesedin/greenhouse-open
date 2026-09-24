from datetime import UTC, datetime

import pytest
from greenhouse_protocol.enums import ObservationType

from greenhouse_adapters.wur.agc4_challenge_2024.compartments import compartment
from greenhouse_adapters.wur.agc4_challenge_2024.timeseries import parse_timeseries

# A compartment file's control columns around the CO2 dosing reset: the
# setpoint and its effective (VIP) value disagree, dosing switches off, and
# the cumulative minutes reset.
CSV = """\
time,compartment/co2_concentration_setpoint,compartment/co2_concentration_vip,compartment/co2_actuation_state,compartment/co2_dosage_minutes_cumulative,compartment/minimum_pipe_temperature_setpoint
2024-10-01 07:35:00+02:00,800.0,650.0,1.0,355.0,35.0
2024-10-01 07:40:00+02:00,800.0,650.0,2.0,0.0,
"""


def _values_at(at: datetime) -> dict[ObservationType, float]:
    observations = parse_timeseries(CSV.splitlines(), compartment("3.06"))
    return {o.observation_type: o.value for o in observations if o.timestamp == at}


def test_effective_values_are_kept_apart_from_their_setpoints() -> None:
    values = _values_at(datetime(2024, 10, 1, 5, 35, tzinfo=UTC))

    assert values[ObservationType.CO2_SETPOINT_PPM] == 800.0
    assert values[ObservationType.CO2_EFFECTIVE_PPM] == 650.0
    assert values[ObservationType.MINIMUM_PIPE_TEMPERATURE_SETPOINT_C] == 35.0
    assert values[ObservationType.CO2_DOSING_MINUTES_SINCE_RESET] == 355.0


def test_co2_actuation_codes_are_recoded_to_on_and_off() -> None:
    assert (
        _values_at(datetime(2024, 10, 1, 5, 35, tzinfo=UTC))[ObservationType.CO2_DOSING_ON] == 1.0
    )
    after_reset = _values_at(datetime(2024, 10, 1, 5, 40, tzinfo=UTC))
    assert after_reset[ObservationType.CO2_DOSING_ON] == 0.0
    assert after_reset[ObservationType.CO2_DOSING_MINUTES_SINCE_RESET] == 0.0


def test_an_unknown_actuation_code_is_refused() -> None:
    unknown = CSV.replace(",2.0,0.0,", ",3.0,0.0,")

    with pytest.raises(ValueError, match="unexpected code"):
        list(parse_timeseries(unknown.splitlines(), compartment("3.06")))
