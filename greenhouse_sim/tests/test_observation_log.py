"""A run's observation log (P06.6): append-only and in the order delivered,
a reading in it only once delivered, each sensor's freshness, and its
cameras' frames as metadata."""

import json
from datetime import timedelta

import pytest
from greenhouse_protocol.enums import CaptureModality

from greenhouse_sim.api.routes import respond
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.sensors.log import SensorFreshness
from greenhouse_sim.services import sensors
from greenhouse_sim.services.sensors import SensorObservations
from greenhouse_sim.world.sensors import Camera

HEATED = {"heater": 1.0}
# The back temperature sensor's 20th sample, taken at 19 min, drops out; the
# samples either side of it do not. Its readings come 30 s late.
DROPPED_AT_S = 19 * 60
LATENCY_S = 30


def _log(until_s: float, *, clean: bool = False) -> SensorObservations:
    return sensors.observations("climate_box", levels=HEATED, until_s=until_s, clean=clean)


def _freshness(until_s: float, sensor_id: str, *, clean: bool = False) -> SensorFreshness:
    return next(f for f in _log(until_s, clean=clean).freshness if f.sensor_id == sensor_id)


def test_the_log_is_append_only_and_in_the_order_delivered() -> None:
    earlier = _log(300).observations
    later = _log(600).observations
    delivered = [o.delivered_at for o in later]

    assert later[: len(earlier)] == earlier
    assert len(later) > len(earlier)
    assert delivered == sorted(d for d in delivered if d is not None)


def test_a_reading_is_in_the_log_only_once_delivered() -> None:
    # The CO2 sensor's readings come a minute after they are taken.
    def co2(until_s: float) -> list[float]:
        log = _log(until_s)
        return [
            (o.timestamp - log.start).total_seconds()
            for o in log.observations
            if o.sensor_id == "co2"
        ]

    assert co2(59) == []
    assert co2(60) == [0.0]
    assert co2(179) == [0.0, 60.0]


def test_the_dropped_sample_is_the_one_the_test_expects() -> None:
    log = _log(DROPPED_AT_S + 2 * 60)
    taken = {
        (o.timestamp - log.start).total_seconds()
        for o in log.observations
        if o.sensor_id == "temperature_back"
    }

    assert DROPPED_AT_S not in taken
    assert {DROPPED_AT_S - 60.0, DROPPED_AT_S + 60.0} <= taken


@pytest.mark.parametrize(
    ("until_s", "due_s", "stale"),
    [
        # Just before the dropped reading is due, the one before it has come.
        (DROPPED_AT_S + LATENCY_S - 1, DROPPED_AT_S - 60, False),
        # Due, and not come, until the next is due.
        (DROPPED_AT_S + LATENCY_S, DROPPED_AT_S, True),
        (DROPPED_AT_S + 60 + LATENCY_S - 1, DROPPED_AT_S, True),
        # The next has come.
        (DROPPED_AT_S + 60 + LATENCY_S, DROPPED_AT_S + 60, False),
    ],
    ids=["before it is due", "once due", "until the next", "the next come"],
)
def test_a_sensor_is_stale_exactly_while_a_due_reading_has_not_come(
    until_s: float, due_s: float, stale: bool
) -> None:
    log = _log(until_s)
    state = next(f for f in log.freshness if f.sensor_id == "temperature_back")

    assert state.stale is stale
    assert state.due_at == log.start + timedelta(seconds=due_s)


def test_a_sensor_is_neither_fresh_nor_stale_before_its_first_reading_is_due() -> None:
    state = _freshness(59, "co2")

    assert (state.due_at, state.latest_at, state.stale) == (None, None, False)
    assert not _freshness(60, "co2").stale


def test_a_clean_sensor_is_never_stale_and_a_sensor_of_nothing_always_is() -> None:
    for until_s in (0, 600, DROPPED_AT_S + LATENCY_S):
        assert not _freshness(until_s, "temperature_front").stale
        # Clean, the back sensor drops nothing and is on time.
        assert not _freshness(until_s, "temperature_back", clean=True).stale
        # No model gives PAR yet.
        assert _freshness(until_s, "par").stale


def test_a_camera_takes_a_frame_every_cadence_and_the_log_records_its_metadata() -> None:
    log = _log(600)
    (camera,) = [
        s for s in SCENARIO_REGISTRY["climate_box"].layout.sensors if isinstance(s, Camera)
    ]

    assert [(f.timestamp - log.start).total_seconds() for f in log.frames] == [
        60.0 * minute for minute in range(11)
    ]
    latest = log.frames[-1]
    assert latest.sensor_id == "front_camera"
    assert latest.frame_id == "sim_front_camera_20260101T001000Z_frame"
    assert (latest.position, latest.target) == (camera.position, camera.target)
    assert latest.rotation == camera.rotation()
    assert latest.intrinsics == camera.intrinsics
    # A frame holds what a camera records; its instance pass is the
    # simulator's truth, and is not one of them.
    assert latest.modalities == (CaptureModality.RGB, CaptureModality.DEPTH)


def test_the_api_serves_the_log_with_its_freshness_and_frames() -> None:
    response = respond("GET", "/api/scenarios/climate_box/climate/observations?set=heater:1&t=600")
    served = SensorObservations.model_validate(response.body)

    assert response.status == 200
    assert served == _log(600)
    assert isinstance(response.body, dict)
    assert '"modalities":["RGB","DEPTH"]' in json.dumps(response.body, separators=(",", ":"))
