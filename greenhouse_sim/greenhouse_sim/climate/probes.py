"""Probes through a climate run, beside the same run with everything off
(P05.7).

At each moment asked, a probe reads the air at its point as the run's field
there samples it (`EnvironmentField.sample`): its temperature, relative
humidity and air speed. It reads the same of the run with every piece of
equipment off, its doors and vents as they are, so that the two can be
charted side by side.
"""

import math
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldGrid
from greenhouse_sim.world.geometry import Vector3


class DrawnAir(Protocol):
    """The air a run draws on its grid at a moment: a grid run's
    (`greenhouse_sim.climate.run.ClimateRun`), or the whole house's, the
    same in every cell (`greenhouse_sim.climate.day.WholeHouseDay`)."""

    @property
    def grid(self) -> FieldGrid: ...

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        """The air at `time_s`, as a field on `grid`, the run's own."""
        ...


class Readings(BaseModel):
    """A probe's readings at each moment: temperature (°C), relative humidity
    (%) and air speed (m/s)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature_c: list[float]
    humidity_pct: list[float]
    speed_m_s: list[float]


class ProbeSeries(BaseModel):
    """A probe's point, and what it reads through the run and through the
    same run with everything off."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    point: Vector3
    controlled: Readings
    all_off: Readings


class ClimateProbes(BaseModel):
    """Probes through a climate run, at each of its moments, in seconds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    times_s: list[float]
    probes: list[ProbeSeries]


def _reading(field: EnvironmentField, quantity: AirQuantity, point: Vector3) -> float:
    value = field.sample(quantity, point)
    if value is None:
        raise ValueError(f"({point.x}, {point.y}, {point.z}) lies outside the house's air")
    if isinstance(value, Vector3):
        return math.sqrt(value.x**2 + value.y**2 + value.z**2)
    return value


def _readings(fields: Sequence[EnvironmentField], point: Vector3) -> Readings:
    return Readings(
        temperature_c=[_reading(field, AirQuantity.TEMPERATURE, point) for field in fields],
        humidity_pct=[_reading(field, AirQuantity.HUMIDITY, point) for field in fields],
        speed_m_s=[_reading(field, AirQuantity.VELOCITY, point) for field in fields],
    )


def probe_series(
    run: DrawnAir, all_off: DrawnAir, points: Sequence[Vector3], times_s: Sequence[float]
) -> ClimateProbes:
    """What probes at `points` read through `run` and `all_off`, at each of
    `times_s`, as the runs' published fields sample it."""
    controlled = [
        EnvironmentField.from_document(run.field("probes", run.grid, t).document()) for t in times_s
    ]
    off = [
        EnvironmentField.from_document(all_off.field("probes", all_off.grid, t).document())
        for t in times_s
    ]
    return ClimateProbes(
        times_s=list(times_s),
        probes=[
            ProbeSeries(
                point=point,
                controlled=_readings(controlled, point),
                all_off=_readings(off, point),
            )
            for point in points
        ],
    )
