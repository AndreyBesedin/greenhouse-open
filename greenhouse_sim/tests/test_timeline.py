"""A run's timeline (P09.2): each process's events at its own cadence, in a
window of the run, in the order they happen; and the same on every run.

The reference greenhouse's second day, its heater on at 1 h into it, and
its right fan on every evening at 18 h.
"""

from collections import Counter
from http import HTTPStatus
from typing import Any

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.processes import Process
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.timeline import TimelineDocument, timeline
from greenhouse_sim.world.sensors import Camera, PointSensor

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
# The processes by name, in the order they take their turns.
TURNS = [process.value for process in Process]
HEATER_ON = ((DAY_S + 3600.0, "heater", 1.0),)
EVENINGS = ((64_800.0, "fan_right", 1.0),)


def _second_day() -> TimelineDocument:
    return timeline(
        RunRequest("reference_greenhouse", commands=HEATER_ON, daily=EVENINGS),
        until_s=2 * DAY_S,
        from_s=DAY_S,
    )


def _counts(document: TimelineDocument) -> Counter[tuple[str, str]]:
    return Counter(
        (document.processes[process], document.subjects[subject])
        for process, subject in zip(document.process, document.subject, strict=True)
    )


def test_over_a_day_each_process_has_its_events_at_its_own_cadence() -> None:
    counts = _counts(_second_day())

    for plant in plant_ids(REFERENCE):
        assert counts[(Process.PLANTS, plant)] == 1
    point_sensors = [s for s in REFERENCE.layout.sensors if isinstance(s, PointSensor)]
    cameras = [s for s in REFERENCE.layout.sensors if isinstance(s, Camera)]
    assert point_sensors and cameras
    for sensor in point_sensors:
        assert counts[(Process.SENSORS, sensor.sensor_id)] == DAY_S / sensor.cadence_s
    for camera in cameras:
        assert counts[(Process.CAMERAS, camera.sensor_id)] == DAY_S / camera.cadence_s
    # Each command once: the heater's, and the fan's on this day.
    assert counts[(Process.COMMANDS, "heater")] == 1
    assert counts[(Process.COMMANDS, "fan_right")] == 1
    # The air a minute at a time, the commands at minutes' ends.
    assert counts[(Process.AIR, "house")] == DAY_S / 60


def test_the_same_run_has_the_same_events_in_the_same_order() -> None:
    assert _second_day() == _second_day()


def test_at_a_moment_commands_go_first_then_the_air_plants_sensors_and_cameras() -> None:
    midnight = 2 * DAY_S
    document = timeline(
        RunRequest("reference_greenhouse", commands=((midnight, "heater", 0.0),)),
        until_s=midnight,
        from_s=DAY_S,
    )
    at_midnight = [
        document.processes[process]
        for time_s, process in zip(document.times_s, document.process, strict=True)
        if time_s == midnight
    ]

    assert list(dict.fromkeys(at_midnight)) == TURNS
    assert at_midnight == sorted(at_midnight, key=TURNS.index)
    assert document.kinds[document.kind[document.times_s.index(midnight)]] == "set to 0"


def test_a_window_is_the_moments_day_by_default_and_the_runs_start_is_in_its_first() -> None:
    later = timeline(RunRequest("climate_box"), until_s=DAY_S + 600.0)
    first = timeline(RunRequest("climate_box"), until_s=600.0)

    assert (later.from_s, later.until_s) == (DAY_S, DAY_S + 600.0)
    assert min(later.times_s) == DAY_S + 60.0
    # The first day's window holds the start: every sensor's first sample.
    assert min(first.times_s) == 0.0
    assert first.subjects[first.subject[0]] == "temperature_front"


def test_a_run_that_works_no_climate_has_no_air_events() -> None:
    document = timeline(RunRequest("sensor_lab"), until_s=600.0)

    assert document.times_s
    assert document.processes.index(Process.AIR) not in document.process


def test_its_route_refuses_a_window_over_a_day_and_commands_as_the_climates() -> None:
    longer = respond("GET", f"/api/scenarios/climate_box/timeline?t={2 * DAY_S:.0f}&from=0")
    late = respond("GET", "/api/scenarios/climate_box/timeline?t=600&daily=86400:heater:1")

    assert (longer.status, longer.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "a timeline's window is a day at most, 86400 s, not 172800"},
    )
    assert (late.status, late.body) == (
        HTTPStatus.BAD_REQUEST,
        {
            "error": "a daily command's time of day lies from 0 to 86400 s, before the next "
            "midnight: 86400"
        },
    )


def _served(query: str) -> dict[str, Any]:
    response = respond("GET", f"/api/scenarios/climate_box/timeline?{query}")
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


def test_its_route_serves_the_document() -> None:
    body = _served("t=600&set=heater:1&schedule=300:fan:1")

    assert body["processes"] == [process.value for process in Process]
    commands = [
        (body["times_s"][at], body["subjects"][subject])
        for at, (process, subject) in enumerate(zip(body["process"], body["subject"], strict=True))
        if process == 0
    ]
    assert commands == [(0.0, "heater"), (300.0, "fan")]
