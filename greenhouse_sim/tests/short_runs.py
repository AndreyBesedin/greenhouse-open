"""What a test of logic runs on: a packaged scenario cut to a few days, so
that it takes seconds where the scenario's own run takes minutes.

The time a run takes goes on the air cell by cell through its first two
hours, on the sun's shadows through each day, and on what its sensors sample,
a whole field for each sample (run under a profiler). So a cut scenario
has its air the whole house's and, unless it keeps its season, a calm,
constant weather under a polar night. It keeps its identifier, and so its
plants' and devices', and its start. A test that holds what the air's grid,
the sun, a season or many plants do runs on the scenario itself, or says so.
"""

from collections.abc import Iterable
from typing import Any, Final

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.site import DEFAULT_SITE

DAYS: Final = 4
# Far enough north that the sun stays under the horizon through the first
# five days of March, and all January: the reference run's and the box's starts.
POLAR_LATITUDE_DEG: Final = 85.0


def cut(
    scenario_id: str,
    *,
    days: int = DAYS,
    plants: tuple[int, int] | None = None,
    season: bool = False,
    sensors: Iterable[str] | None = None,
    **changes: Any,
) -> ScenarioConfig:
    """The packaged scenario `scenario_id`, its runs `days` long, its air the
    whole house's, `plants` rows and columns of plants if named, only the
    `sensors` named if any are; under its own site and weather if it keeps
    its `season`, and otherwise in the dark; and with `changes` to the rest
    of its configuration."""
    config = SCENARIO_REGISTRY[scenario_id]
    air = config.climate.model_dump(exclude={"kind", "mixing_m2_s"})
    cuts: dict[str, Any] = {
        "duration_days": days,
        "climate": {"kind": "whole_house", **air},
    }
    if plants is not None:
        cuts |= {"rows": plants[0], "columns": plants[1]}
    if not season:
        cuts |= {
            "site": DEFAULT_SITE.model_copy(update={"latitude_deg": POLAR_LATITUDE_DEG}),
            "weather": ConstantWeather(),
        }
    if sensors is not None:
        named = set(sensors)
        layout = config.layout.model_dump()
        layout["sensors"] = [s for s in layout["sensors"] if s["sensor_id"] in named]
        cuts["layout"] = layout
    return ScenarioConfig.model_validate(config.model_dump() | cuts | changes)


def simulator_of(*configs: ScenarioConfig, **given: Any) -> Simulator:
    """A simulator that knows `configs` in place of the packaged scenarios of
    their identifiers, and of any other identifier beside them, made with
    `given`."""
    packaged = PACKAGED
    for config in configs:
        if config.greenhouse_id in PACKAGED.ids():
            packaged = packaged.with_config(config)
    made = Simulator(Catalogue(packaged), **given)
    for config in configs:
        if config.greenhouse_id not in PACKAGED.ids():
            made.catalogue.register(config)
    return made
