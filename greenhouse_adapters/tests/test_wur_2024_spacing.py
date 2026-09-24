from datetime import UTC, datetime

from greenhouse_protocol.enums import EventSource, EventType, ObservationType

from greenhouse_adapters.wur.agc4_challenge_2024.compartments import compartment
from greenhouse_adapters.wur.agc4_challenge_2024.spacing import spacing_events
from greenhouse_adapters.wur.agc4_challenge_2024.timeseries import parse_timeseries

# reference.csv's shape: the density is written only on the day it takes
# effect, at local midnight.
CSV = """\
time,compartment/air_temperature,dwarf_tomato/plant_density
2024-09-03 00:00:00+02:00,19.0,56.0
2024-09-10 23:55:00+02:00,19.5,
2024-09-11 00:00:00+02:00,19.4,42.0
2024-09-19 00:00:00+02:00,19.2,30.0
"""


def test_plant_density_is_observed_only_on_the_rows_that_record_it() -> None:
    observations = list(parse_timeseries(CSV.splitlines(), compartment("3.06")))

    densities = [
        (o.timestamp, o.value)
        for o in observations
        if o.observation_type == ObservationType.PLANT_DENSITY_PER_M2
    ]
    assert densities == [
        (datetime(2024, 9, 2, 22, tzinfo=UTC), 56.0),
        (datetime(2024, 9, 10, 22, tzinfo=UTC), 42.0),
        (datetime(2024, 9, 18, 22, tzinfo=UTC), 30.0),
    ]
    assert all(o.compartment_id == "3.06" for o in observations)


def test_each_density_change_after_the_first_is_a_spacing_event() -> None:
    observations = list(parse_timeseries(CSV.splitlines(), compartment("3.06")))

    events = list(spacing_events(observations, compartment("3.06")))

    assert [(e.timestamp, e.parameters) for e in events] == [
        (
            datetime(2024, 9, 10, 22, tzinfo=UTC),
            {"plant_density_before_per_m2": 56.0, "plant_density_after_per_m2": 42.0},
        ),
        (
            datetime(2024, 9, 18, 22, tzinfo=UTC),
            {"plant_density_before_per_m2": 42.0, "plant_density_after_per_m2": 30.0},
        ),
    ]
    assert all(e.event_type == EventType.SPACING for e in events)
    assert all(e.source == EventSource.CONTROL_SYSTEM for e in events)
    assert all(e.compartment_id == "3.06" and e.plant_id is None for e in events)
    assert events[0].event_id == "wur24_c306_20240910T220000Z_spacing"


def test_a_repeated_density_is_not_a_spacing_event() -> None:
    repeated = CSV.replace("42.0", "56.0")
    observations = list(parse_timeseries(repeated.splitlines(), compartment("3.06")))

    events = list(spacing_events(observations, compartment("3.06")))

    assert [e.parameters["plant_density_after_per_m2"] for e in events] == [30.0]


def test_another_compartments_densities_are_ignored() -> None:
    observations = list(parse_timeseries(CSV.splitlines(), compartment("3.06")))

    assert list(spacing_events(observations, compartment("3.08"))) == []
