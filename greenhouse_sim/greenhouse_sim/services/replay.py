"""A run's state probes, day by day, and their digests (P09.5): what tells
one replay of a run from another.

At the end of each of a run's days, its state is probed:

- **its crop,** where it grows one organ by organ: each plant's structure,
  every organ and its size, and its history (`greenhouse_sim.core.crop`);
- **its house's air** then (`greenhouse_sim.climate.house`);
- **a sample of its readings:** what each of its point sensors observed on
  each hour of the day, on the observation path, its noise and dropouts and
  all (`greenhouse_sim.services.sensors`).

The probe is written as JSON with its numbers rounded to
`ROUNDED_DECIMALS`, and to `SIGNIFICANT_DIGITS` where that is coarser, so
that the last bits in which two machines' maths libraries differ do not
tell two replays apart, however large the number, and digested. The same run
gives the same digests on every replay; a run changed from a moment on
gives the same digests for the days before it. A test replays the reference
run's first days against the digests kept in the repository
(`tests/fixtures/reference_replay.json`).
"""

import json
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop import run_crop
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import observations
from greenhouse_sim.units import HOUR_S, HOURS_A_DAY

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# Probes' numbers are rounded to this many decimals before they are digested,
# and to this many significant digits: a season's heat in joules has eleven
# digits before its point, its last decimals the machine's, not the run's.
ROUNDED_DECIMALS: Final = 6
SIGNIFICANT_DIGITS: Final = 12
# How many hexadecimal digits of a probe's digest are kept.
DIGEST_LENGTH: Final = 16


class DayProbe(BaseModel):
    """A run's state probed at the end of its day `day`: the digest of the
    probe, and, to read beside it, the house's air temperature and relative
    humidity then, the crop's organs and mean thermal time, and the
    readings sampled."""

    model_config = ConfigDict(frozen=True)

    day: int
    digest: str
    house_temperature_c: float
    house_humidity_pct: float
    organs: int
    thermal_time_cd: float
    readings: int


def _rounded(value: JsonValue) -> JsonValue:
    if isinstance(value, float):
        return float(f"{round(value, ROUNDED_DECIMALS):.{SIGNIFICANT_DIGITS}g}")
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def day_probes(simulator: Simulator, run: RunRequest, days: int) -> list[DayProbe]:
    """A run's state probed at the end of each of its first `days` days,
    asked for as its climate field is."""
    config = scenario(simulator.catalogue, run.scenario_id)
    _, climate = climate_run(simulator, run)
    crop = run_crop(simulator, run) if config.crop_model == CropModel.ORGAN else None
    probes = []
    for day in range(days):
        end = (day + 1) * DAY_S
        air = climate.house.air_at(end)
        plants = [] if crop is None else list(crop.plants_on(day + 1))
        readings: list[JsonValue] = [
            [observation.sensor_id, (hour + 1) * HOUR_S, observation.value]
            for hour in range(HOURS_A_DAY)
            for observation in observations(
                simulator,
                run,
                until_s=day * DAY_S + (hour + 1) * HOUR_S,
                from_s=day * DAY_S + (hour + 1) * HOUR_S - 1.0,
            ).observations
        ]
        probe: JsonValue = _rounded(
            {
                "day": day,
                "house": [air.temperature_c, air.humidity_g_kg, air.co2_ppm],
                "plants": [plant.model_dump(mode="json") for plant in plants],
                "readings": readings,
            }
        )
        text = json.dumps(probe, sort_keys=True, separators=(",", ":"))
        organs = sum(1 for plant in plants for _ in plant.organs())
        probes.append(
            DayProbe(
                day=day,
                digest=short_digest(text, DIGEST_LENGTH),
                house_temperature_c=round(air.temperature_c, 2),
                house_humidity_pct=round(air.relative_humidity_pct(), 1),
                organs=organs,
                thermal_time_cd=round(sum(plant.thermal_time for plant in plants) / len(plants), 2)
                if plants
                else 0.0,
                readings=len(readings),
            )
        )
    return probes
