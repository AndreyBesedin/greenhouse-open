"""The sensor lab (P06.7): still air warming linearly along a small house, a
known truth. Its clean sensors read it exactly, its imperfect one errs as
its configuration says, the same way every time, and its camera looks at
boxes that partly hide one another, or, in its `blocked` layout, at one box
hiding the others."""

import itertools
import statistics

import pytest

from greenhouse_sim.airflow.prescribed import GradientAirflow
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.services import sensors
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.sensors import Camera, PointSensor

LAB = SCENARIO_REGISTRY["sensor_lab"]
HOUR_S = 3600.0
# How far a statistic of the imperfect sensor's errors may stray from its
# configured value, in its standard errors.
STANDARD_ERRORS = 3


def _gradient() -> GradientAirflow:
    assert isinstance(LAB.airflow, GradientAirflow)
    return LAB.airflow


def _sensor(sensor_id: str) -> PointSensor:
    sensor = next(s for s in LAB.layout.sensors if s.sensor_id == sensor_id)
    assert isinstance(sensor, PointSensor)
    return sensor


def _readings(sensor_id: str) -> list[tuple[float, float, float]]:
    """Each of a sensor's readings through the run: when it was taken and
    delivered, in seconds from the start, and its value."""
    log = sensors.observations("sensor_lab", until_s=HOUR_S)
    return [
        (
            (o.timestamp - log.start).total_seconds(),
            ((o.delivered_at or o.timestamp) - log.start).total_seconds(),
            o.value,
        )
        for o in log.observations
        if o.sensor_id == sensor_id
    ]


def test_the_lab_air_warms_linearly_along_the_house() -> None:
    assert _gradient().temperature_at(0.0) == 16.0
    assert _gradient().temperature_at(12.0) == 22.0
    assert LAB.layout.equipment == []


@pytest.mark.parametrize("sensor_id", ["clean_front", "clean_back"])
def test_a_clean_sensor_reads_the_gradient_exactly(sensor_id: str) -> None:
    sensor = _sensor(sensor_id)
    expected = _gradient().temperature_at(sensor.position.x)
    readings = _readings(sensor_id)
    truth = next(
        t for t in sensors.truth("sensor_lab", until_s=HOUR_S).sensors if t.sensor_id == sensor_id
    )

    # A sample every minute, on time, each the line's value where it stands.
    assert [taken for taken, _, _ in readings] == [60.0 * minute for minute in range(61)]
    assert all(delivered == taken for taken, delivered, _ in readings)
    assert [value for _, _, value in readings] == pytest.approx([expected] * 61, abs=1e-9)
    assert truth.values == pytest.approx([expected] * 61, abs=1e-9)


def test_the_imperfect_sensor_errs_as_its_configuration_says() -> None:
    sensor = _sensor("imperfect_front")
    imperfections = sensor.imperfections
    truth = _gradient().temperature_at(sensor.position.x)
    readings = _readings("imperfect_front")
    taken = [moment for moment, _, _ in readings]
    errors = [value - truth for _, _, value in readings]

    # Bias and drift: the errors' line through the run, fitted.
    fit = statistics.linear_regression(taken, errors)
    residuals = [
        error - (fit.intercept + fit.slope * moment)
        for moment, error in zip(taken, errors, strict=True)
    ]
    spread = statistics.stdev(residuals)
    # The fit's standard errors, for noise of the configured spread.
    count = len(readings)
    times_spread = statistics.pstdev(taken)
    slope_error = imperfections.noise_sd / (count**0.5 * times_spread)
    intercept_error = (
        imperfections.noise_sd
        * ((1 + (statistics.fmean(taken) / times_spread) ** 2) / count) ** 0.5
    )
    assert fit.slope * HOUR_S == pytest.approx(
        imperfections.drift_per_hour, abs=STANDARD_ERRORS * slope_error * HOUR_S
    )
    assert fit.intercept == pytest.approx(imperfections.bias, abs=STANDARD_ERRORS * intercept_error)
    # Noise: what is left, rounded to the sensor's tenths.
    assert spread == pytest.approx(imperfections.noise_sd, rel=0.3)
    assert all(round(value * 10) == pytest.approx(value * 10) for _, _, value in readings)
    # Latency: each delivered 30 s after it was taken.
    assert all(delivered - moment == imperfections.latency_s for moment, delivered, _ in readings)
    # Dropout: a tenth of its 61 samples, give or take.
    assert 61 - count == 6


def test_the_lab_errs_the_same_way_every_time() -> None:
    assert _readings("imperfect_front") == _readings("imperfect_front")


def _silhouette(camera: Camera, layout: Layout, fixture_id: str) -> tuple[float, ...]:
    """The box around where a fixture's corners land on the camera's picture:
    its least and greatest u, then v."""
    fixture = next(f for f in layout.fixtures() if f.fixture_id == fixture_id)
    low, high = fixture.bounds()
    corners = [
        camera.project(Vector3(x=x, y=y, z=z))
        for x, y, z in itertools.product((low.x, high.x), (low.y, high.y), (low.z, high.z))
    ]
    us = [c[0] for c in corners if c is not None]
    vs = [c[1] for c in corners if c is not None]
    return (min(us), max(us), min(vs), max(vs))


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def _contains(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] <= b[0] and b[1] <= a[1] and a[2] <= b[2] and b[3] <= a[3]


def test_the_camera_sees_boxes_partly_hiding_one_another() -> None:
    layout = LAB.layout
    (camera,) = [s for s in layout.sensors if isinstance(s, Camera)]
    near, middle, far = (
        _silhouette(camera, layout, name) for name in ("box_near", "box_middle", "box_far")
    )

    for front, behind in ((near, middle), (middle, far)):
        assert _overlap(front, behind)
        assert not _contains(front, behind)


def test_its_blocked_layout_moves_the_near_box_to_hide_the_others() -> None:
    layout = load_layout("sensor_lab", "blocked")
    (camera,) = [s for s in layout.sensors if isinstance(s, Camera)]
    near = _silhouette(camera, layout, "box_near")

    assert _contains(near, _silhouette(camera, layout, "box_middle"))
    assert _contains(near, _silhouette(camera, layout, "box_far"))
