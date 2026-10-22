"""A scenario's runs' checkpoints (P09.5), as a client saves, lists,
downloads and uploads them.

A checkpoint is a run's state at the start of one of its days:

- **the run it belongs to:** its scenario, and the version of the
  scenario's manifest it was made with; its layout and weather, by name;
  its equipment's levels and its doors' and vents' openings from the start;
  the commands it gave before that day, and its target changes (#274); and
  its daily commands, or none given, for its scenario's own;
- **its house's air** then (`greenhouse_sim.climate.house`), and an hour
  before its day began, where the field of the day's first hour starts its
  grid run from (`greenhouse_sim.climate.day.window_start`): without it, a
  run restored would work out every day before to draw its first hour;
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
API forgets them, and the API writes no file. A scenario's manifest may
name a day of its run as its opening day, kept in the repository as a
checkpoint beside it, gzipped: the API keeps it as it starts
(`load_openings`), beside the others and never evicted, so that its run's
later days need not be worked out from its start. A run that agrees with one up
to its moment takes its state over (`greenhouse_sim.services.kept_states`):
restoring a checkpoint is asking for its run again, and a branch from it is
the same run with other commands from its moment on.
"""

import dataclasses
import gzip
import json
import math
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue, NonNegativeInt, ValidationError

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.development import daily_thermal_time
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT, TRANSPLANT_CD
from greenhouse_sim.climate.day import window_start
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.climate.psychrometrics import saturation_ratio_g_kg
from greenhouse_sim.core.clock import DAY_S, days_ended
from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scenarios.manifest_files import manifest_digest, opening_day, opening_file
from greenhouse_sim.services.crop import run_crop, seed_kept_crops
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.fields import (
    climate_run,
    run_schedule,
    seed_kept_climate_runs,
)
from greenhouse_sim.services.kept_states import KeptState, drop, keep
from greenhouse_sim.services.runs import Commanded, RunRequest, checked_moment
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, plant_ids, scenario
from greenhouse_sim.services.stores import Store

# The format a checkpoint is written in, which a reader refuses if it does
# not know it: 3 since a checkpoint keeps its run's target changes (#274).
CHECKPOINT_FORMAT: Final = 3
# The format before, read as this one: a format 2 checkpoint's run changed
# no target.
READ_AS_CURRENT: Final = 2
# How many checkpoints are kept, the last saved or uploaded.
KEPT_CHECKPOINTS: Final = 16
# How many hexadecimal digits of its content's digest name a checkpoint.
ID_LENGTH: Final = 16
# What a house's air may be, in an uploaded checkpoint: colder or warmer
# than any greenhouse's air, or richer in CO₂ than any enrichment, is not a
# state a run reaches.
COLDEST_AIR_C: Final = -60.0
WARMEST_AIR_C: Final = 80.0
MOST_CO2_PPM: Final = 20_000.0
# How far a plant's thermal time may be from the sum of the days it lived,
# relative to it: what adding them up in another order gives.
THERMAL_TIME_TOLERANCE: Final = 1e-9


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
    # The target changes its run made before its day (#274), each its
    # moment, target and value in °C (format 3).
    targets: list[Commanded] = []
    day: NonNegativeInt
    house: HouseAir
    # Its house's air an hour before its day began, where its day's first
    # hour draws its field from (`greenhouse_sim.climate.day.window_start`),
    # so that a run restored works out none of the days before; none on its
    # run's first day, which draws its first hours from its start (format 2).
    house_before: HouseAir | None = None
    plants: list[Plant] = []
    # What each plant experienced on each day before, by plant.
    lived: list[dict[str, LocalEnvironment]] = []

    def identifier(self) -> str:
        """A digest of its content, which names it."""
        return short_digest(self.model_dump_json(), ID_LENGTH)

    def run(self) -> RunRequest:
        """Its run, as a client would ask for it, up to its day: the
        commands it keeps are those before it."""
        return RunRequest(
            self.scenario_id,
            layout=self.layout,
            weather=self.weather,
            levels=self.levels,
            openings=self.openings,
            commands=tuple(self.commands),
            daily=None if self.daily is None else tuple(self.daily),
            targets=tuple(self.targets),
        )


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
    targets: list[Commanded]
    day: int
    time_s: float
    plants: int


# The last `KEPT_CHECKPOINTS` saved or uploaded, and beside them, pinned,
# never in their place, the scenarios' opening days: they are the oldest,
# and the next fresh run of their scenario would work its days out from the
# start without them. A checkpoint let go takes its state with it.
# Each with the state it was kept with: let go, it takes that state with it,
# and not one the same checkpoint, uploaded again meanwhile, keeps since.
CHECKPOINTS: Store[str, tuple[Checkpoint, KeptState]] = Store(
    "checkpoints", KEPT_CHECKPOINTS, on_drop=lambda key, kept: drop(key, kept[1]), label=str
)


def save_checkpoint(run: RunRequest, time_s: float = 0.0) -> CheckpointSummary:
    """A checkpoint of a run, asked for as its climate field is, at the
    start of the day `time_s` lies in, or ends: its state then, worked out
    if it has not been, kept."""
    scenario_id = run.scenario_id
    config = scenario(scenario_id)
    checked_moment(config, time_s)
    day = days_ended(time_s)
    moment = day * DAY_S
    _, climate = climate_run(run)
    plants: list[Plant] = []
    lived: list[dict[str, LocalEnvironment]] = []
    if config.crop_model == CropModel.ORGAN:
        crop = run_crop(run)
        plants = list(crop.plants_on(day))
        lived = crop.lived_through(day)
    before = window_start(moment)
    checkpoint = Checkpoint(
        scenario_id=scenario_id,
        manifest=manifest_digest(scenario_id),
        layout=run.layout or DEFAULT_LAYOUT,
        weather=run.weather or DEFAULT_WEATHER,
        levels=dict(run.levels),
        openings=dict(run.openings),
        commands=[command for command in run.commands if command[0] < moment],
        daily=None if run.daily is None else list(run.daily),
        targets=[change for change in run.targets if change[0] < moment],
        day=day,
        house=climate.house.air_at(moment),
        house_before=climate.house.air_at(before) if before < moment else None,
        plants=plants,
        lived=lived,
    )
    return _kept(checkpoint)


def checkpoints() -> list[CheckpointSummary]:
    """The checkpoints kept, the earliest saved first."""
    return [_summary(checkpoint_id, kept) for checkpoint_id, (kept, _) in CHECKPOINTS.values()]


def checkpoint(checkpoint_id: str) -> Checkpoint:
    """A checkpoint kept, as it is downloaded."""
    found = CHECKPOINTS.get(checkpoint_id)
    if found is None:
        raise NotFound(f"no checkpoint {checkpoint_id!r}: restarting the API forgets them")
    return found[0]


def upload_checkpoint(document: JsonValue) -> CheckpointSummary:
    """A checkpoint uploaded, checked, and kept. Refused if it is not one,
    is in a format this simulator does not read, was made with another
    version of its scenario's manifest, or does not fit its scenario's run."""
    return _kept(_checked_upload(document))


def _checked_upload(document: JsonValue) -> Checkpoint:
    """A checkpoint uploaded, checked as `upload_checkpoint` says."""
    if isinstance(document, dict):
        written_in = document.get("checkpoint_format")
        if written_in == READ_AS_CURRENT:
            if "targets" in document:
                raise InvalidRequest("a format 2 checkpoint keeps no target changes")
            document = document | {"checkpoint_format": CHECKPOINT_FORMAT}
        elif written_in != CHECKPOINT_FORMAT:
            raise InvalidRequest(
                f"a checkpoint in format {written_in!r}; this simulator reads format "
                f"{CHECKPOINT_FORMAT}, and format {READ_AS_CURRENT} as it"
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
    if (uploaded.house_before is None) != (window_start(uploaded.day * DAY_S) == 0.0):
        raise InvalidRequest(
            "a checkpoint keeps its house's air an hour before its day, after its run's "
            "first day, and only then"
        )
    climate_run(uploaded.run())
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
    problems = _implausible(uploaded)
    if problems:
        raise InvalidRequest(f"a checkpoint no run reaches: {problems[0]}")
    return uploaded


def _implausible(checkpoint: Checkpoint) -> list[str]:
    """What, in a checkpoint that fits its run's shape, no run could have
    reached: air out of bounds, a plant that breaks the structure's rules,
    or one whose thermal time is not what the days it lived add up to."""
    problems = [
        f"its house's air {when}: {problem}"
        for when, air in (("on its day", checkpoint.house), ("before it", checkpoint.house_before))
        if air is not None
        for problem in _air_problems(air)
    ]
    for day, lived in enumerate(checkpoint.lived):
        for plant_id, environment in lived.items():
            if not all(map(math.isfinite, environment.model_dump().values())):
                problems.append(f"what {plant_id} lived on day {day} is not finite")
    if problems:
        return problems
    for plant in checkpoint.plants:
        problems += [f"{plant.plant_id}: {problem}" for problem in plant.problems()]
        added = TRANSPLANT_CD + sum(
            daily_thermal_time(day[plant.plant_id].mean_temperature_c, DEVELOPMENT)
            for day in checkpoint.lived
        )
        if not math.isclose(plant.thermal_time, added, rel_tol=THERMAL_TIME_TOLERANCE):
            problems.append(
                f"{plant.plant_id}'s thermal time is {plant.thermal_time:.6g} °Cd, and the "
                f"{checkpoint.day} days it lived add up to {added:.6g}"
            )
    return problems


def _air_problems(air: HouseAir) -> list[str]:
    if not all(map(math.isfinite, dataclasses.astuple(air))):
        return ["it is not finite"]
    problems = []
    if not COLDEST_AIR_C <= air.temperature_c <= WARMEST_AIR_C:
        problems.append(f"{air.temperature_c:g} °C")
    saturated = float(saturation_ratio_g_kg(air.temperature_c))
    if not 0.0 <= air.humidity_g_kg <= saturated:
        problems.append(f"{air.humidity_g_kg:g} g/kg of water, saturated at {saturated:g}")
    if not 0.0 <= air.co2_ppm <= MOST_CO2_PPM:
        problems.append(f"{air.co2_ppm:g} ppm of CO₂")
    if air.removed_kg < 0 or air.condensed_kg < 0:
        problems.append("it has lost less than no water")
    return problems


def opening_bytes(checkpoint: Checkpoint) -> bytes:
    """A checkpoint as a scenario's kept opening day holds it: its JSON,
    gzipped the same way every time it is written."""
    return gzip.compress(checkpoint.model_dump_json().encode(), mtime=0)


def load_opening(scenario_id: str) -> list[CheckpointSummary]:
    """Keep a scenario's opening day, as its manifest names it and the files
    beside it hold it (`opening_file`): its run's checkpoint, and the same
    run's with everything off, which a viewer charts beside it, each
    uploaded, so that both runs' later days carry on from them. None if it
    names none; refused, as an upload is, if one does not fit its run."""
    if opening_day(scenario_id) is None:
        return []
    return [
        _kept(
            _checked_upload(
                json.loads(gzip.decompress(opening_file(scenario_id, off).read_bytes()))
            ),
            opening=True,
        )
        for off in (False, True)
    ]


def load_openings() -> list[str]:
    """Keep every scenario's opening day that fits its run, as the API
    starts; the reasons the others are refused, by scenario."""
    refused = []
    for scenario_id in SCENARIO_REGISTRY:
        try:
            load_opening(scenario_id)
        except ServiceError as error:
            refused.append(f"{scenario_id}'s opening day: {error.message}")
    return refused


def _kept(checkpoint: Checkpoint, *, opening: bool = False) -> CheckpointSummary:
    """Keep a checkpoint, and its state for the runs that agree with it; a
    scenario's opening day beside the others, never evicted."""
    checkpoint_id = checkpoint.identifier()
    state = KeptState(
        house=(
            checkpoint.scenario_id,
            checkpoint.layout,
            checkpoint.weather,
            tuple(sorted(checkpoint.openings.items())),
        ),
        schedule=run_schedule(checkpoint.run()),
        day=checkpoint.day,
        air=checkpoint.house,
        plants=tuple(checkpoint.plants),
        lived=tuple(checkpoint.lived),
        earlier=(
            ()
            if checkpoint.house_before is None
            else ((window_start(checkpoint.day * DAY_S), checkpoint.house_before),)
        ),
    )
    # Its state first, so that a checkpoint listed always has one.
    keep(checkpoint_id, state)
    CHECKPOINTS.keep(checkpoint_id, (checkpoint, state), pinned=opening)
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
        targets=checkpoint.targets,
        day=checkpoint.day,
        time_s=checkpoint.day * DAY_S,
        plants=len(checkpoint.plants),
    )
