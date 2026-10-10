"""The simulator's scenarios: which there are, how each is laid out, and what
it looks like before its first day, changed as a client asks.

A client may see a scenario with another of its layouts, under another
weather (`greenhouse_sim.weather.presets`), its greenhouse's dimensions
changed, its doors and vents standing open, and its equipment running.
Every change is checked as the scenario's own description is: a layout or
weather it does not have is not found, and a greenhouse its layout or
openings no longer fit, a ridge below the eaves, or a level for equipment
it does not have, is refused with the reason.
"""

import math
from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, JsonValue, ValidationError

from greenhouse_sim.core.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import (
    DEFAULT_LAYOUT,
    layout_document,
    layout_names,
    load_layout,
)
from greenhouse_sim.scene.snapshot import SceneSnapshot, scene_snapshot
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.weather.presets import PRESETS
from greenhouse_sim.weather.recorded import recorded_weathers

# The envelope's dimensions a client may change.
DIMENSIONS: Final = ("length", "width", "spans", "bays", "eave_height", "ridge_height")
# The name of a scenario's own weather, beside the presets'.
DEFAULT_WEATHER: Final = "default"
# A weather's name may end with this and a cloud cover in %, which overrides
# its own, for QA.
CLOUDS_MARK: Final = "@"
MOST_CLOUD_PCT: Final = 100.0


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    plants: int
    duration_days: int
    # Its layouts' names, its default first.
    layouts: list[str]
    # The weathers it can be run under, by name, its own first.
    weathers: list[str]


class SceneChanges(BaseModel):
    """How a client asks to see a scenario changed: with another of its
    layouts, under another weather, its greenhouse's dimensions set by name,
    its doors and vents open by a fraction from 0 to 1, and its equipment run
    at a level from 0 to 1, each by identifier."""

    layout: str = DEFAULT_LAYOUT
    weather: str = DEFAULT_WEATHER
    envelope: dict[str, float] = {}
    openings: dict[str, float] = {}
    levels: dict[str, float] = {}


def scenario_summaries() -> list[ScenarioSummary]:
    """Every registered scenario, as a client lists them."""
    return [
        ScenarioSummary(
            id=config.greenhouse_id,
            name=config.name,
            description=config.description,
            plants=config.rows * config.columns,
            duration_days=config.duration_days,
            layouts=layout_names(config.greenhouse_id),
            weathers=weather_names(),
        )
        for config in SCENARIO_REGISTRY.values()
    ]


def weather_names() -> list[str]:
    """The weathers any scenario can be run under: its own, then the
    presets, then the recorded ones."""
    return [DEFAULT_WEATHER, *PRESETS, *recorded_weathers()]


def scenario(scenario_id: str) -> ScenarioConfig:
    """A registered scenario."""
    config = SCENARIO_REGISTRY.get(scenario_id)
    if config is None:
        raise NotFound(f"no scenario {scenario_id!r}")
    return config


def plant_ids(config: ScenarioConfig) -> list[str]:
    """The identifiers of a scenario's whole crop: rows times columns plants."""
    plant_count = config.rows * config.columns
    return [f"{config.greenhouse_id}_plant_{i:03d}" for i in range(1, plant_count + 1)]


def initial_scene(scenario_id: str, changes: SceneChanges | None = None) -> SceneSnapshot:
    """A scenario's full crop before its first day, as a viewer draws it,
    with the changes a client asks for."""
    changes = changes or SceneChanges()
    config = changed(scenario(scenario_id), changes)
    world = SimulationEngine(config).initialize(
        plant_ids(config), greenhouse_id=config.greenhouse_id
    )
    return scene_snapshot(world, config, equipment_levels(config, changes.levels))


def layout(scenario_id: str, name: str = DEFAULT_LAYOUT) -> dict[str, JsonValue]:
    """One of a scenario's layouts, as its file holds it, once it is checked
    to fit the scenario."""
    return layout_document(_with_layout(scenario(scenario_id), name).layout)


def equipment_levels(config: ScenarioConfig, levels: Mapping[str, float]) -> dict[str, float]:
    """The levels asked for a scenario's equipment, checked: a level for
    equipment it does not have, or outside 0 to 1, is refused."""
    known = {piece.actuator_id for piece in config.layout.equipment}
    unknown = sorted(set(levels) - known)
    if unknown:
        named = ", ".join(map(repr, unknown))
        raise InvalidRequest(f"{config.greenhouse_id} has no equipment {named}")
    outside = sorted(name for name, level in levels.items() if not 0.0 <= level <= 1.0)
    if outside:
        raise InvalidRequest(f"a level runs from 0 to 1: {', '.join(outside)}")
    return dict(levels)


def changed(config: ScenarioConfig, changes: SceneChanges) -> ScenarioConfig:
    """A scenario with the changes a client asks for: another of its layouts
    and another weather, then its greenhouse's dimensions and openings."""
    return _with_envelope(
        _with_weather(_with_layout(config, changes.layout), changes.weather), changes
    )


def _with_weather(config: ScenarioConfig, name: str) -> ScenarioConfig:
    """The scenario under a preset or a recorded weather, or its own; any
    other is not found. A name may end with `@` and a cloud cover, from 0 to
    100 %, which overrides the weather's (`cold_spring_day@80`): a QA
    override of how clouded its sky is (P08.7); any other is refused."""
    base, override, clouds = name.partition(CLOUDS_MARK)
    if override:
        try:
            cover = float(clouds)
        except ValueError:
            cover = math.nan
        if not 0.0 <= cover <= MOST_CLOUD_PCT:
            raise InvalidRequest(f"a cloud cover runs from 0 to 100 %, not {clouds!r}")
        return _with_weather(config, base).model_copy(update={"cloud_cover_pct": cover})
    if name == DEFAULT_WEATHER:
        return config
    weather = PRESETS.get(name) or recorded_weathers().get(name)
    if weather is None:
        known = ", ".join(weather_names())
        raise NotFound(f"there is no weather {name!r}; there are {known}")
    return config.model_copy(update={"weather": weather})


def _with_layout(config: ScenarioConfig, name: str) -> ScenarioConfig:
    """The scenario with another of its layouts, read from its file: one it
    does not have is not found, and one that does not fit its greenhouse or
    crop is refused."""
    if name == DEFAULT_LAYOUT:
        return config
    try:
        other = load_layout(config.greenhouse_id, name)
    except KeyError:
        raise NotFound(f"{config.greenhouse_id} has no layout {name!r}") from None
    try:
        return ScenarioConfig.model_validate(config.model_dump() | {"layout": other})
    except ValidationError as error:
        raise InvalidRequest(f"no such layout: {error.errors()[0]['msg']}") from None


def _with_envelope(config: ScenarioConfig, changes: SceneChanges) -> ScenarioConfig:
    """The scenario with its greenhouse's dimensions and openings changed. The
    envelope is checked afresh, as any description of a greenhouse is: an
    opening that no longer fits, a ridge below the eaves, or a greenhouse the
    scenario's layout no longer fits in, is refused."""
    unknown_sizes = sorted(set(changes.envelope) - set(DIMENSIONS))
    if unknown_sizes:
        named = ", ".join(map(repr, unknown_sizes))
        raise InvalidRequest(f"the envelope has no {named}; it has {', '.join(DIMENSIONS)}")
    envelope = config.envelope
    known = {opening.opening_id for opening in envelope.openings}
    unknown = sorted(set(changes.openings) - known)
    if unknown:
        named = ", ".join(map(repr, unknown))
        raise InvalidRequest(f"{config.greenhouse_id} has no opening {named}")
    if not changes.envelope and not changes.openings:
        return config
    opened = [
        opening.model_dump()
        | {"opening": changes.openings.get(opening.opening_id, opening.opening)}
        for opening in envelope.openings
    ]
    try:
        reshaped = type(envelope).model_validate(
            envelope.model_dump() | changes.envelope | {"openings": opened}
        )
        return ScenarioConfig.model_validate(config.model_dump() | {"envelope": reshaped})
    except ValidationError as error:
        raise InvalidRequest(f"no such greenhouse: {error.errors()[0]['msg']}") from None
