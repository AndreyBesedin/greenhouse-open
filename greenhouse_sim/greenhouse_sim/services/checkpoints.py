"""A scenario's runs' checkpoints (P09.5), as a client saves, lists,
downloads and uploads them.

A checkpoint is a run's state at the start of one of its days:

- **the run it belongs to:** its scenario, and the version of the
  scenario's manifest it was made with; its layout and weather, by name;
  its equipment's levels and its doors' and vents' openings from the start;
  the commands it gave before that day; and its daily commands, or none
  given, for its scenario's own;
- **its house's air** then (`greenhouse_sim.climate.house`);
- **its crop,** where it grows one organ by organ: its plants then, and what
  each experienced on each day before (`greenhouse_sim.core.crop`).

Nothing else needs keeping: its sensors' and cameras' draws are seeded
sample by sample, its weather and its sun are functions of the moment, and
its air cell by cell is drawn again from the house's. Runs are
deterministic, so a checkpoint holds nothing its run could not work out
again: it saves the time to work it out, and it lets a run carry on from a
state made on another machine, or with other code.

Checkpoints are kept in the API's memory, the last `KEPT_CHECKPOINTS`
saved or uploaded, each named by a digest of its content; restarting the
API forgets them, and the API writes no file. A run that agrees with one up
to its moment takes its state over (`greenhouse_sim.services.kept_states`):
restoring a checkpoint is asking for its run again, and a branch from it is
the same run with other commands from its moment on.
"""

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue, NonNegativeInt, ValidationError

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S, days_ended
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scenarios.manifest_files import manifest_digest
from greenhouse_sim.services.crop import run_crop, seed_kept_crops
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.fields import (
    Commanded,
    climate_run,
    run_schedule,
    seed_kept_climate_runs,
)
from greenhouse_sim.services.kept_states import KeptState, drop, keep
from greenhouse_sim.services.runs import checked_moment
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, plant_ids, scenario

# The format a checkpoint is written in, which a reader refuses if it does
# not know it.
CHECKPOINT_FORMAT: Final = 1
# How many checkpoints are kept, the last saved or uploaded.
KEPT_CHECKPOINTS: Final = 16
# How many hexadecimal digits of its content's digest name a checkpoint.
ID_LENGTH: Final = 16


class Checkpoint(BaseModel):
    """A run's state at the start of its day `day`, as it is downloaded and
    uploaded: its run, its house's air, and its organ-level crop, if it
    grows one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_format: int = CHECKPOINT_FORMAT
    scenario_id: str
    # The digest of its scenario's manifest (`manifest_digest`).
    manifest: str
    layout: str = DEFAULT_LAYOUT
    weather: str = DEFAULT_WEATHER
    levels: dict[str, float] = {}
    openings: dict[str, float] = {}
    # The commands the run gave before its day, each its moment, actuator
    # and level; and its daily commands, or none given, for its scenario's.
    commands: list[Commanded] = []
    daily: list[Commanded] | None = None
    day: NonNegativeInt
    house: HouseAir
    plants: list[Plant] = []
    # What each plant experienced on each day before, by plant.
    lived: list[dict[str, LocalEnvironment]] = []

    def identifier(self) -> str:
        """A digest of its content, which names it."""
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:ID_LENGTH]


class CheckpointSummary(BaseModel):
    """A checkpoint as a client lists it: its identifier, its run's parts,
    its day and moment, and how many plants it keeps."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    scenario_id: str
    layout: str
    weather: str
    levels: dict[str, float]
    openings: dict[str, float]
    commands: list[Commanded]
    daily: list[Commanded] | None
    day: int
    time_s: float
    plants: int


_KEPT: OrderedDict[str, Checkpoint] = OrderedDict()
_KEEPING = threading.Lock()


def forget_checkpoints() -> None:
    """Forget every checkpoint kept, and the states runs took from them."""
    with _KEEPING:
        for checkpoint_id in _KEPT:
            drop(checkpoint_id)
        _KEPT.clear()


def save_checkpoint(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
) -> CheckpointSummary:
    """A checkpoint of a scenario's run, asked for as its climate field is,
    at the start of the day `time_s` lies in, or ends: its state then,
    worked out if it has not been, kept."""
    config = scenario(scenario_id)
    checked_moment(config, time_s)
    day = days_ended(time_s)
    moment = day * DAY_S
    _, climate = climate_run(scenario_id, layout, levels, openings, commands, weather, daily)
    plants: list[Plant] = []
    lived: list[dict[str, LocalEnvironment]] = []
    if config.crop_model == CropModel.ORGAN:
        crop = run_crop(scenario_id, layout, levels, openings, commands, weather, daily)
        plants = list(crop.plants_on(day))
        lived = crop.lived_through(day)
    checkpoint = Checkpoint(
        scenario_id=scenario_id,
        manifest=manifest_digest(scenario_id),
        layout=layout or DEFAULT_LAYOUT,
        weather=weather or DEFAULT_WEATHER,
        levels=dict(levels or {}),
        openings=dict(openings or {}),
        commands=[command for command in commands if command[0] < moment],
        daily=None if daily is None else list(daily),
        day=day,
        house=climate.house.air_at(moment),
        plants=plants,
        lived=lived,
    )
    return _kept(checkpoint)


def checkpoints() -> list[CheckpointSummary]:
    """The checkpoints kept, the earliest saved first."""
    with _KEEPING:
        kept = list(_KEPT.items())
    return [_summary(checkpoint_id, checkpoint) for checkpoint_id, checkpoint in kept]


def checkpoint(checkpoint_id: str) -> Checkpoint:
    """A checkpoint kept, as it is downloaded."""
    with _KEEPING:
        found = _KEPT.get(checkpoint_id)
    if found is None:
        raise NotFound(f"no checkpoint {checkpoint_id!r}: restarting the API forgets them")
    return found


def upload_checkpoint(document: JsonValue) -> CheckpointSummary:
    """A checkpoint uploaded, checked, and kept. Refused if it is not one,
    is in a format this simulator does not read, was made with another
    version of its scenario's manifest, or does not fit its scenario's run."""
    if isinstance(document, dict) and document.get("checkpoint_format") != CHECKPOINT_FORMAT:
        raise InvalidRequest(
            f"a checkpoint in format {document.get('checkpoint_format')!r}; this simulator "
            f"reads format {CHECKPOINT_FORMAT}"
        )
    try:
        uploaded = Checkpoint.model_validate(document)
    except ValidationError as error:
        raise InvalidRequest(f"not a checkpoint: {error.errors()[0]['msg']}") from None
    config = scenario(uploaded.scenario_id)
    if uploaded.manifest != manifest_digest(uploaded.scenario_id):
        raise InvalidRequest(
            f"a checkpoint made with another version of {uploaded.scenario_id}'s manifest"
        )
    if uploaded.day > config.duration_days:
        raise InvalidRequest(
            f"a run of {uploaded.scenario_id} has days 0 to {config.duration_days}, "
            f"not {uploaded.day}"
        )
    climate_run(
        uploaded.scenario_id,
        uploaded.layout,
        uploaded.levels,
        uploaded.openings,
        uploaded.commands,
        uploaded.weather,
        uploaded.daily,
    )
    expected = plant_ids(config) if config.crop_model == CropModel.ORGAN else []
    if [plant.plant_id for plant in uploaded.plants] != expected:
        raise InvalidRequest(f"a checkpoint's plants are {uploaded.scenario_id}'s, in order")
    if config.crop_model == CropModel.ORGAN and (
        len(uploaded.lived) != uploaded.day
        or any(set(day) != set(expected) for day in uploaded.lived)
    ):
        raise InvalidRequest(
            f"a crop on day {uploaded.day} has lived {uploaded.day} days, each plant's"
        )
    return _kept(uploaded)


def _kept(checkpoint: Checkpoint) -> CheckpointSummary:
    """Keep a checkpoint, and its state for the runs that agree with it."""
    checkpoint_id = checkpoint.identifier()
    state = KeptState(
        house=(
            checkpoint.scenario_id,
            checkpoint.layout,
            checkpoint.weather,
            tuple(sorted(checkpoint.openings.items())),
        ),
        schedule=run_schedule(
            checkpoint.scenario_id,
            checkpoint.layout,
            checkpoint.levels,
            checkpoint.commands,
            checkpoint.daily,
        ),
        day=checkpoint.day,
        air=checkpoint.house,
        plants=tuple(checkpoint.plants),
        lived=tuple(checkpoint.lived),
    )
    with _KEEPING:
        _KEPT[checkpoint_id] = checkpoint
        _KEPT.move_to_end(checkpoint_id)
        keep(checkpoint_id, state)
        while len(_KEPT) > KEPT_CHECKPOINTS:
            oldest, _ = _KEPT.popitem(last=False)
            drop(oldest)
    seed_kept_climate_runs(state)
    seed_kept_crops(state)
    return _summary(checkpoint_id, checkpoint)


def _summary(checkpoint_id: str, checkpoint: Checkpoint) -> CheckpointSummary:
    return CheckpointSummary(
        checkpoint_id=checkpoint_id,
        scenario_id=checkpoint.scenario_id,
        layout=checkpoint.layout,
        weather=checkpoint.weather,
        levels=checkpoint.levels,
        openings=checkpoint.openings,
        commands=checkpoint.commands,
        daily=checkpoint.daily,
        day=checkpoint.day,
        time_s=checkpoint.day * DAY_S,
        plants=len(checkpoint.plants),
    )
