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
- **its models:** each part's model and version (decision 0054), and the
  state of those that keep one: its crop's, its plants then, organ by organ
  or as the simple crop keeps them, and what each experienced on each day
  before (`greenhouse_sim.core.crop`). A checkpoint is restored only into a
  run of the same models and versions.

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
from typing import TYPE_CHECKING, Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    model_validator,
)

from greenhouse_sim.climate.day import window_start
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.climate.psychrometrics import saturation_ratio_g_kg
from greenhouse_sim.core.clock import DAY_S, days_ended
from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scenarios.manifest_files import opening_file
from greenhouse_sim.scenarios.registry import ModelRun, models_run
from greenhouse_sim.services.climate_runs import climate_run, run_schedule, seed_kept_climate_runs
from greenhouse_sim.services.crop import scenario_crop, seed_kept_crops
from greenhouse_sim.services.crop_models import (
    CROP_MODELS,
    CropModelState,
    CropState,
    SimpleCropState,
    registration,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError, first_reason
from greenhouse_sim.services.kept_states import KeptState, keep
from greenhouse_sim.services.runs import (
    Commanded,
    RunPlan,
    RunRequest,
    checked_crop_plan,
    checked_moment,
)
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    SceneChanges,
    changed,
    plant_ids,
    scenario,
    version,
    with_weather,
)
from greenhouse_sim.services.stores import Store

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# The format a checkpoint is written in, which a reader refuses if it does
# not know it: 9 since its house's air keeps how each of its controller's
# loops stands, its vents' stage beside its heater (P11.2), as 8 named its
# controller's part (P14.6), 7 its house's air and 6 its sunlight and
# sensors.
CHECKPOINT_FORMAT: Final = 9
# The formats before, each read as the one after it: a format 2
# checkpoint's run changed no target (#274); a format 3 checkpoint's
# commands, daily commands and target changes are its run's plan; a format
# 4 checkpoint's plants are its organ crop's state; a format 5, 6 or 7
# checkpoint names the parts there were then, the others its run's at the
# version every model had then (P14.2); and a format 8 checkpoint's run, whose
# controller ran its heater alone, had its vents' every stage shut.
WITHOUT_TARGETS: Final = 2
WITH_COMMANDS: Final = 3
WITHOUT_MODELS: Final = 4
WITH_FOUR_PARTS: Final = 5
WITH_SIX_PARTS: Final = 6
WITH_SEVEN_PARTS: Final = 7
WITH_THE_HEATER_ALONE: Final = 8
READ_AS_CURRENT: Final = (
    WITHOUT_TARGETS,
    WITH_COMMANDS,
    WITHOUT_MODELS,
    WITH_FOUR_PARTS,
    WITH_SIX_PARTS,
    WITH_SEVEN_PARTS,
    WITH_THE_HEATER_ALONE,
)
# The parts a checkpoint of each format with models names, every one of
# them: a part left out would leave its model and version unchecked.
NAMED_BY: Final = {
    WITH_FOUR_PARTS: (Part.WEATHER, Part.AIR_FIELD, Part.CROP, Part.CROP_WALK),
    WITH_SIX_PARTS: (
        Part.WEATHER,
        Part.AIR_FIELD,
        Part.CROP,
        Part.CROP_WALK,
        Part.SUNLIGHT,
        Part.SENSORS,
    ),
    WITH_SEVEN_PARTS: (
        Part.WEATHER,
        Part.AIR_FIELD,
        Part.CROP,
        Part.CROP_WALK,
        Part.SUNLIGHT,
        Part.SENSORS,
        Part.HOUSE_AIR,
    ),
    WITH_THE_HEATER_ALONE: tuple(Part),
    CHECKPOINT_FORMAT: tuple(Part),
}
# The version every model had before a checkpoint kept models' versions.
FIRST_VERSION: Final = 1
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


class ModelState(BaseModel):
    """A part's model as a checkpoint keeps it: its name and version, and
    its state then, if it keeps one, as the crop's models do."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    version: PositiveInt
    state: CropState | SimpleCropState | None = None


class Checkpoint(BaseModel):
    """A run's state at the start of its day `day`, as it is downloaded and
    uploaded: its run, its house's air, and its models, with the state of
    those that keep one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_format: int = CHECKPOINT_FORMAT
    scenario_id: str
    # Its scenario's version: its manifest's digest, if packaged
    # (`CatalogueEntry.version`).
    manifest: str
    layout: str = DEFAULT_LAYOUT
    weather: str = DEFAULT_WEATHER
    levels: dict[str, float] = {}
    openings: dict[str, float] = {}
    # Its run's plan as it stood for the days before: its actions before its
    # day, and what it does every day, or None for its scenario's own
    # (format 4).
    plan: RunPlan = RunPlan()
    day: NonNegativeInt
    house: HouseAir
    # Its house's air an hour before its day began, where its day's first
    # hour draws its field from (`greenhouse_sim.climate.day.window_start`),
    # so that a run restored works out none of the days before; none on its
    # run's first day, which draws its first hours from its start (format 2).
    house_before: HouseAir | None = None
    # Each part's model and version, and its state then, if it keeps one
    # (format 5), for every part. A checkpoint of an earlier format names its
    # crop's alone: its others are its run's, at the version every model had
    # then.
    models: dict[Part, ModelState]

    @model_validator(mode="before")
    @classmethod
    def _its_crops_state_is_its_models(cls, given: Any) -> Any:
        """Its crop's state, read as its crop's model keeps it."""
        models = given.get("models") if isinstance(given, dict) else None
        if not isinstance(models, dict):
            return given
        crop = models.get(Part.CROP.value)
        if not isinstance(crop, dict) or not isinstance(crop.get("state"), dict):
            return given
        kept = CROP_MODELS.get(str(crop.get("model")))
        if kept is None:
            return given
        state = kept.state.model_validate(crop["state"])
        return given | {"models": models | {Part.CROP.value: crop | {"state": state}}}

    @property
    def crop(self) -> CropState | SimpleCropState:
        """Its crop's plants and the days they lived, or none."""
        kept = self.models.get(Part.CROP)
        return CropState() if kept is None or kept.state is None else kept.state

    def identifier(self) -> str:
        """A digest of its content, which names it."""
        return short_digest(self.model_dump_json(), ID_LENGTH)

    def run(self) -> RunRequest:
        """Its run, as a client would ask for it, up to its day: the
        actions its plan keeps are those before it."""
        return RunRequest(
            self.scenario_id,
            layout=self.layout,
            weather=self.weather,
            levels=self.levels,
            openings=self.openings,
            plan=self.plan,
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


def new_store(states: Store[str, KeptState]) -> Store[str, tuple[Checkpoint, KeptState]]:
    """A simulator's checkpoints (decision 0048): the last `KEPT_CHECKPOINTS`
    saved or uploaded, and beside them, pinned, never in their place, the
    scenarios' opening days: they are the oldest, and the next fresh run of
    their scenario would work its days out from the start without them.
    Each with the state it was kept with, in `states`: let go, it takes that
    state with it, and not one the same checkpoint, uploaded again
    meanwhile, keeps since."""
    return Store(
        "checkpoints",
        KEPT_CHECKPOINTS,
        on_drop=lambda key, kept: states.drop(key, kept[1]),
        label=str,
    )


def save_checkpoint(
    simulator: Simulator, run: RunRequest, time_s: float = 0.0
) -> CheckpointSummary:
    """A checkpoint of a run, asked for as its climate field is, at the
    start of the day `time_s` lies in, or ends: its state then, worked out
    if it has not been, kept."""
    scenario_id = run.scenario_id
    config = scenario(simulator.catalogue, scenario_id)
    checked_moment(config, time_s)
    day = days_ended(time_s)
    moment = day * DAY_S
    _, climate = climate_run(simulator, run)
    crop = scenario_crop(simulator, run)
    state: CropModelState = registration(config).state(
        plants=list(crop.plants_on(day)), lived=crop.lived_through(day)
    )
    before = window_start(moment)
    checkpoint = Checkpoint(
        scenario_id=scenario_id,
        manifest=version(simulator.catalogue, scenario_id),
        layout=run.layout or DEFAULT_LAYOUT,
        weather=run.weather or DEFAULT_WEATHER,
        levels=dict(run.levels),
        openings=dict(run.openings),
        plan=run.plan.before(moment).validated(),
        day=day,
        house=climate.house.air_at(moment),
        house_before=climate.house.air_at(before) if before < moment else None,
        models={
            part: ModelState(
                model=ran.model, version=ran.version, state=state if part is Part.CROP else None
            )
            for part, ran in _models_run(simulator, run).items()
        },
    )
    return _kept(simulator, checkpoint)


def _models_run(simulator: Simulator, run: RunRequest) -> dict[Part, ModelRun]:
    """Each part's model and version a run runs: its scenario's, under the
    weather it is asked for, which may be another model's."""
    config = scenario(simulator.catalogue, run.scenario_id)
    return models_run(with_weather(config, run.weather or DEFAULT_WEATHER))


def checkpoints(simulator: Simulator) -> list[CheckpointSummary]:
    """The checkpoints kept, the earliest saved first."""
    return [
        _summary(checkpoint_id, kept) for checkpoint_id, (kept, _) in simulator.checkpoints.values()
    ]


def checkpoint(simulator: Simulator, checkpoint_id: str) -> Checkpoint:
    """A checkpoint kept, as it is downloaded."""
    found = simulator.checkpoints.get(checkpoint_id)
    if found is None:
        raise NotFound(f"no checkpoint {checkpoint_id!r}: restarting the API forgets them")
    return found[0]


def upload_checkpoint(simulator: Simulator, document: JsonValue) -> CheckpointSummary:
    """A checkpoint uploaded, checked, and kept. Refused if it is not one,
    is in a format this simulator does not read, was made with another
    version of its scenario's manifest, or does not fit its scenario's run."""
    return _kept(simulator, _checked_upload(simulator, document))


def read_checkpoint(document: JsonValue) -> Checkpoint:
    """A checkpoint as it is written, in this simulator's format or one it
    reads as it (`READ_AS_CURRENT`), as this format holds it. Refused if it
    is not one, or is in a format this simulator does not read."""
    # A checkpoint of this format names every part's model, one of format 5,
    # 6 or 7 every part's there was then, and one of an earlier format its
    # crop's alone.
    format_given = document.get("checkpoint_format") if isinstance(document, dict) else None
    named = NAMED_BY.get(format_given) if isinstance(format_given, int) else None
    if isinstance(document, dict):
        written_in = document.get("checkpoint_format")
        if written_in != CHECKPOINT_FORMAT and written_in not in READ_AS_CURRENT:
            *earlier, last = (str(each) for each in READ_AS_CURRENT)
            read = f"{', '.join(earlier)} and {last}" if earlier else last
            raise InvalidRequest(
                f"a checkpoint in format {written_in!r}; this simulator reads format "
                f"{CHECKPOINT_FORMAT}, and formats {read} as it"
            )
        if written_in == WITHOUT_TARGETS:
            if "targets" in document:
                raise InvalidRequest("a format 2 checkpoint keeps no target changes")
            written_in = WITH_COMMANDS
        if written_in == WITH_COMMANDS:
            document = _planned(document)
            written_in = WITHOUT_MODELS
        if written_in == WITHOUT_MODELS:
            document = _with_models(document)
        if written_in in (
            WITH_FOUR_PARTS,
            WITH_SIX_PARTS,
            WITH_SEVEN_PARTS,
            WITH_THE_HEATER_ALONE,
        ):
            document = document | {"checkpoint_format": CHECKPOINT_FORMAT}
    try:
        held = Checkpoint.model_validate(document)
    except ValidationError as error:
        raise InvalidRequest(f"not a checkpoint: {first_reason(error)}") from None
    unnamed = [part.value for part in named or () if part not in held.models]
    if unnamed:
        raise InvalidRequest(
            f"not a checkpoint: a format {format_given} checkpoint keeps each part's model, "
            f"and this one none for the {', '.join(unnamed)}"
        )
    return held


def _checked_upload(simulator: Simulator, document: JsonValue) -> Checkpoint:
    """A checkpoint uploaded, checked as `upload_checkpoint` says."""
    uploaded = read_checkpoint(document)
    config = scenario(simulator.catalogue, uploaded.scenario_id)
    if uploaded.manifest != version(simulator.catalogue, uploaded.scenario_id):
        raise InvalidRequest(
            f"a checkpoint made with another version of {uploaded.scenario_id}'s manifest"
        )
    runs = _models_run(simulator, uploaded.run())
    for part, ran in runs.items():
        # A checkpoint of an earlier format names its crop's model alone:
        # its others are its run's, at the version every model had then.
        kept = uploaded.models.get(part) or ModelState(model=ran.model, version=FIRST_VERSION)
        if (kept.model, kept.version) != (ran.model, ran.version):
            raise InvalidRequest(
                f"a checkpoint made with the {kept.model} model of the {part}, version "
                f"{kept.version}: its run's is the {ran.model} model, version {ran.version}"
            )
    # Kept, it names every part's model, as one saved does, so that it
    # downloads as one of this format and uploads again.
    uploaded = uploaded.model_copy(
        update={
            "models": {
                part: uploaded.models.get(part) or ModelState(model=ran.model, version=ran.version)
                for part, ran in runs.items()
            }
        }
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
    climate_run(simulator, uploaded.run())
    checked_crop_plan(
        changed(simulator.catalogue, config, SceneChanges(layout=uploaded.layout)), uploaded.plan
    )
    expected = plant_ids(config)
    if [plant.plant_id for plant in uploaded.crop.plants] != expected:
        raise InvalidRequest(f"a checkpoint's plants are {uploaded.scenario_id}'s, in order")
    if len(uploaded.crop.lived) != uploaded.day or any(
        set(day) != set(expected) for day in uploaded.crop.lived
    ):
        raise InvalidRequest(
            f"a crop on day {uploaded.day} has lived {uploaded.day} days, each plant's"
        )
    venting = None if config.control is None else config.control.venting
    stages = 0 if venting is None else len(venting.stages)
    for air in (uploaded.house, uploaded.house_before):
        if air is not None and not 0 <= air.vent_stage <= stages:
            raise InvalidRequest(
                f"a checkpoint's vents stand open at stage {air.vent_stage}, and its run's "
                f"have {stages}"
            )
    problems = _implausible(uploaded)
    if problems:
        raise InvalidRequest(f"a checkpoint no run reaches: {problems[0]}")
    return uploaded


def _implausible(checkpoint: Checkpoint) -> list[str]:
    """What, in a checkpoint that fits its run's shape, no run could have
    reached: air out of bounds, what a plant lived not finite, or a crop
    its model does not reach (`CropRegistration.implausible`)."""
    problems = [
        f"its house's air {when}: {problem}"
        for when, air in (("on its day", checkpoint.house), ("before it", checkpoint.house_before))
        if air is not None
        for problem in _air_problems(air)
    ]
    for day, lived in enumerate(checkpoint.crop.lived):
        for plant_id, environment in lived.items():
            if not all(map(math.isfinite, environment.model_dump().values())):
                problems.append(f"what {plant_id} lived on day {day} is not finite")
    if problems:
        return problems
    kept = checkpoint.models.get(Part.CROP)
    crop = None if kept is None else CROP_MODELS.get(kept.model)
    return [] if crop is None else crop.implausible(checkpoint.crop, checkpoint.day)


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


def load_opening(simulator: Simulator, scenario_id: str) -> list[CheckpointSummary]:
    """Keep a scenario's opening day, as its manifest names it and the files
    beside it hold it (`opening_file`): its run's checkpoint, and the same
    run's with everything off, which a viewer charts beside it, each
    uploaded, so that both runs' later days carry on from them. None if it
    names none; refused, as an upload is, if one does not fit its run."""
    entry = simulator.catalogue.entry(scenario_id)
    if entry is None or entry.opening_day is None:
        return []
    return [
        _kept(
            simulator,
            _checked_upload(
                simulator, json.loads(gzip.decompress(opening_file(scenario_id, off).read_bytes()))
            ),
            opening=True,
        )
        for off in (False, True)
    ]


def load_openings(simulator: Simulator) -> list[str]:
    """Keep every scenario's opening day that fits its run, as the API
    starts; the reasons the others are refused, by scenario."""
    refused = []
    for scenario_id in simulator.catalogue.ids():
        try:
            load_opening(simulator, scenario_id)
        except ServiceError as error:
            refused.append(f"{scenario_id}'s opening day: {error.message}")
    return refused


def _kept(
    simulator: Simulator, checkpoint: Checkpoint, *, opening: bool = False
) -> CheckpointSummary:
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
        schedule=run_schedule(simulator.catalogue, checkpoint.run()),
        day=checkpoint.day,
        air=checkpoint.house,
        plants=tuple(checkpoint.crop.plants),
        lived=tuple(checkpoint.crop.lived),
        earlier=(
            ()
            if checkpoint.house_before is None
            else ((window_start(checkpoint.day * DAY_S), checkpoint.house_before),)
        ),
        crop_actions=checkpoint.plan.before(checkpoint.day * DAY_S).crop_plan(),
    )
    # Its state first, so that a checkpoint listed always has one.
    keep(simulator, checkpoint_id, state)
    simulator.checkpoints.keep(checkpoint_id, (checkpoint, state), pinned=opening)
    seed_kept_climate_runs(simulator, state)
    seed_kept_crops(simulator, state)
    return _summary(checkpoint_id, checkpoint)


def _planned(document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """A format 3 checkpoint as format 4 writes it: its commands, daily
    commands and target changes, its run's plan of them. Refused, as any
    checkpoint that is not one, if they are not what format 3 wrote."""
    if "plan" in document:
        raise InvalidRequest("not a checkpoint: a format 3 checkpoint keeps no plan")
    commands = _written(document.get("commands", []))
    daily = None if document.get("daily") is None else _written(document["daily"])
    targets = _written(document.get("targets", []))
    plan: dict[str, JsonValue] = {
        "actions": [
            *({"at_s": at, "action": _set_level(device, level)} for at, device, level in commands),
            *(
                {"at_s": at, "action": {"kind": "set_target", "target": name, "value_c": value}}
                for at, name, value in targets
            ),
        ],
        "daily": None
        if daily is None
        else [
            {"time_of_day_s": time, "action": _set_level(device, level)}
            for time, device, level in daily
        ],
    }
    kept = {name: value for name, value in document.items() if name not in _FORMAT_3_PLAN}
    return kept | {"checkpoint_format": WITHOUT_MODELS, "plan": plan}


def _with_models(document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """A format 4 checkpoint as format 5 writes it: its plants and the days
    they lived, the organ crop's state, at the version every model had
    then; a checkpoint with no plants, the simple crop's. Its other parts'
    models it did not name: its run's are taken for them, at the version
    every model had then (`_checked_upload`)."""
    if "models" in document:
        raise InvalidRequest("not a checkpoint: a format 4 checkpoint keeps no models")
    plants, lived = document.get("plants", []), document.get("lived", [])
    crop: dict[str, JsonValue] = (
        {
            "model": CropModel.ORGAN.value,
            "version": FIRST_VERSION,
            "state": {"plants": plants, "lived": lived},
        }
        if plants
        else {"model": CropModel.SIMPLE.value, "version": FIRST_VERSION}
    )
    kept = {name: value for name, value in document.items() if name not in _FORMAT_4_CROP}
    return kept | {"checkpoint_format": CHECKPOINT_FORMAT, "models": {Part.CROP.value: crop}}


# What a format 4 checkpoint wrote of its crop beside its run.
_FORMAT_4_CROP: Final = ("plants", "lived")


# What a format 3 checkpoint wrote of its run's plan.
_FORMAT_3_PLAN: Final = ("commands", "daily", "targets")


def _written(entries: JsonValue) -> list[list[JsonValue]]:
    """Commands as format 3 wrote them: a list of a moment, a name and a
    number each, refused otherwise."""
    if not isinstance(entries, list) or not all(
        isinstance(entry, list) and len(entry) == len(_COMMANDED) for entry in entries
    ):
        raise InvalidRequest(
            "not a checkpoint: its commands, daily commands and target changes are each a "
            "moment, a name and a number"
        )
    return [entry for entry in entries if isinstance(entry, list)]


# A command's parts, as format 3 wrote each.
_COMMANDED: Final = ("moment", "name", "number")


def _set_level(device_id: JsonValue, level: JsonValue) -> dict[str, JsonValue]:
    return {"kind": "set_level", "device_id": device_id, "level": level}


def _listed(commanded: tuple[Commanded, ...] | None) -> list[Commanded] | None:
    return None if commanded is None else list(commanded)


def _summary(checkpoint_id: str, checkpoint: Checkpoint) -> CheckpointSummary:
    return CheckpointSummary(
        checkpoint_id=checkpoint_id,
        scenario_id=checkpoint.scenario_id,
        layout=checkpoint.layout,
        weather=checkpoint.weather,
        levels=checkpoint.levels,
        openings=checkpoint.openings,
        commands=list(checkpoint.plan.commanded()),
        daily=_listed(checkpoint.plan.daily_commanded()),
        targets=list(checkpoint.plan.targeted()),
        day=checkpoint.day,
        time_s=checkpoint.day * DAY_S,
        plants=len(checkpoint.crop.plants),
    )
