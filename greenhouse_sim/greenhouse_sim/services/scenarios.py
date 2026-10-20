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
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from greenhouse_sim.biology.tomato.organ.transplants import transplant
from greenhouse_sim.climate.commands import DailyCommand
from greenhouse_sim.core.engine import SimulationEngine
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import (
    DEFAULT_LAYOUT,
    layout_document,
    layout_names,
    load_layout,
)
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION as MANIFEST_FORMAT
from greenhouse_sim.scenarios.manifest_files import manifest_digest, opening_day
from greenhouse_sim.scene.plants import crop_entities
from greenhouse_sim.scene.snapshot import SceneSnapshot, greenhouse_scene, scene_snapshot
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.weather.presets import PRESETS
from greenhouse_sim.weather.recorded import recorded_weathers
from greenhouse_sim.world.moves import Move, moved

# The envelope's dimensions a client may change.
DIMENSIONS: Final = ("length", "width", "spans", "bays", "eave_height", "ridge_height")
# The name of a scenario's own weather, beside the presets'.
DEFAULT_WEATHER: Final = "default"
# A weather's name may end with this and a cloud cover in %, which overrides
# its own, for QA.
CLOUDS_MARK: Final = "@"
MOST_CLOUD_PCT: Final = 100.0
# And then with this and a bearing, which overrides its wind's direction.
WIND_MARK: Final = "~"
# What follows it in a layout's name are moves of its equipment and sensors
# (#209): `default~heater:1.2:-0.4`.
MOVES_MARK: Final = "~"
FULL_TURN_DEG: Final = 360.0


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    plants: int
    duration_days: int
    # How its runs grow its crop: "simple" or "organ" (`CropModel`).
    crop_model: str
    # The commands its runs give at a time of day, every day, unless a run
    # gives its own.
    daily: list[DailyCommand]
    # Its doors and vents, by identifier, which commands open as they set its
    # equipment.
    openings: list[str]
    # The day of its run where a viewer opens it, kept as a checkpoint, if
    # its manifest names one.
    opening_day: int | None = None
    # Its layouts' names, its default first.
    layouts: list[str]
    # The weathers it can be run under, by name, its own first.
    weathers: list[str]
    # The heater a thermostat runs by the house's air, if it has one
    # (`climate.thermostat`).
    thermostat: str | None = None


class RunManifest(BaseModel):
    """What a scenario's run is made from, as QA mode shows it (P09.6): its
    manifest's format and version, its seed and days, and the models it
    runs, under the weather the run is asked for."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    # The format its manifest is written in, and what tells this version of
    # it from another (`manifest_digest`).
    schema_version: int
    version: str
    random_seed: int
    start_date: date
    duration_days: int
    opening_day: int | None
    # How it grows its crop ("simple" or "organ") and which variety; how its
    # air moves until a solver says otherwise, the prescribed pattern's kind.
    crop_model: str
    variety: str
    airflow: str
    # The weather the run is under, by name, its own being "default", and
    # its kind ("constant", "synthetic" or "recorded"); its clouds and its
    # wind's direction where QA overrides them.
    weather: str
    weather_kind: str
    cloud_cover_pct: float | None
    wind_from_deg: float | None


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
            crop_model=config.crop_model.value,
            daily=config.daily,
            openings=[opening.opening_id for opening in config.envelope.openings],
            opening_day=opening_day(config.greenhouse_id),
            layouts=layout_names(config.greenhouse_id),
            weathers=weather_names(),
            thermostat=None if config.thermostat is None else config.thermostat.actuator_id,
        )
        for config in SCENARIO_REGISTRY.values()
    ]


def run_manifest(scenario_id: str, weather: str | None = None) -> RunManifest:
    """What a scenario's run is made from, read from its manifest: under its
    own weather, or another asked for as a climate run's is, with its clouds
    and wind overridden."""
    name = weather or DEFAULT_WEATHER
    config = changed(scenario(scenario_id), SceneChanges(weather=name))
    return RunManifest(
        scenario_id=scenario_id,
        schema_version=MANIFEST_FORMAT,
        version=manifest_digest(scenario_id),
        random_seed=config.random_seed,
        start_date=config.start_date,
        duration_days=config.duration_days,
        opening_day=opening_day(scenario_id),
        crop_model=config.crop_model.value,
        variety=config.variety,
        airflow=config.airflow.kind,
        weather=name.partition(WIND_MARK)[0].partition(CLOUDS_MARK)[0],
        weather_kind=config.weather.kind,
        cloud_cover_pct=config.cloud_cover_pct,
        wind_from_deg=config.wind_from_deg,
    )


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
    with the changes a client asks for: its transplants organ by organ,
    where it grows its crop so, or else the simple model's plants."""
    changes = changes or SceneChanges()
    config = changed(scenario(scenario_id), changes)
    levels = equipment_levels(config, changes.levels)
    if config.crop_model == CropModel.ORGAN:
        house = greenhouse_scene(
            config.greenhouse_id, config.envelope, layout=config.layout, levels=levels
        )
        crop = crop_entities(
            [transplant(plant_id, config.random_seed) for plant_id in plant_ids(config)],
            config.layout.trainings(),
            config.envelope,
        )
        return house.model_copy(update={"entities": [*house.entities, *crop]})
    world = SimulationEngine(config).initialize(
        plant_ids(config), greenhouse_id=config.greenhouse_id
    )
    return scene_snapshot(world, config, levels)


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
    override of how clouded its sky is (P08.7); and then with `~` and a
    compass bearing, from 0 to 360°, the wind's direction, which overrides
    the weather's (`default~90`, `cold_spring_day@80~270`, P09.4); any other
    is refused."""
    rest, winded, wind = name.partition(WIND_MARK)
    if winded:
        try:
            bearing = float(wind)
        except ValueError:
            bearing = math.nan
        if not 0.0 <= bearing < FULL_TURN_DEG:
            raise InvalidRequest(f"a wind blows from a bearing from 0 to 360°, not {wind!r}")
        return _with_weather(config, rest).model_copy(update={"wind_from_deg": bearing})
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


def _moves(text: str) -> list[Move]:
    """Moves as an address writes them: `heater:1.2:-0.4,fan_left:0:2`, each
    an item and its displacement along the world's x and y, in metres."""
    moves = []
    for written in text.split(","):
        item_id, *by = written.split(":")
        try:
            dx, dy = (float(value) for value in by)
        except ValueError:
            dx = dy = math.nan
        if not item_id or not (math.isfinite(dx) and math.isfinite(dy)):
            raise InvalidRequest(
                f"a move is an item and two distances, item:dx:dy, not {written!r}"
            )
        moves.append(Move(item_id=item_id, dx_m=dx, dy_m=dy))
    return moves


def _with_layout(config: ScenarioConfig, name: str) -> ScenarioConfig:
    """The scenario with another of its layouts, read from its file: one it
    does not have is not found, and one that does not fit its greenhouse or
    crop is refused. A name may end with `~` and moves of its equipment and
    sensors across the floor (`default~heater:1.2:-0.4`, #209,
    `greenhouse_sim.world.moves`): the layout with them moved, refused as
    any layout is if they no longer fit."""
    base, marked, written = name.partition(MOVES_MARK)
    if marked:
        laid_out = _with_layout(config, base)
        try:
            layout = moved(laid_out.layout, laid_out.envelope.origin, _moves(written))
        except ValueError as error:
            raise InvalidRequest(str(error)) from None
        try:
            return ScenarioConfig.model_validate(
                laid_out.model_dump() | {"layout": layout.model_dump()}
            )
        except ValidationError as error:
            found = error.errors()[0]["msg"].removeprefix("Value error, ")
            raise InvalidRequest(f"moved so, {found}") from None
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
