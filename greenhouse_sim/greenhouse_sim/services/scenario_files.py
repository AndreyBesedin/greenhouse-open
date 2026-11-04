"""A scenario as a file: downloaded, and uploaded, registered and kept
(P17.11).

An upload validates the file (`greenhouse_sim.scenarios.scenario_files`),
registers its scenario as a draft's run is (decision 0048) and, with a run
store, keeps the file beside it, so that a simulator started on the store
registers the scenario again. It never starts a run: it answers the house and
the run settings, for the setup builder to open. A scenario under a recorded
weather the file does not carry and this process does not offer is not
registered; the answer names the weather.

An upload may also be an installation's file, which has no run settings. The
simulator says which of the two a file is, since only its readers know what
each holds. An installation's is read and answered as the builder's import is
(`services.builder.assess`), for the builder to open and give it its run's
settings; nothing is registered, and no draft is kept or changed.

An epoch of a scenario that is not packaged carries its file too (decision
0067): written beside the uploaded ones when the epoch is started, with its
recording inside, and named by its manifest, so that a worker needs only the
store (`carry`, `take_up`). A simulator started on the store knows these
scenarios again as it knows the uploaded ones.
"""

import logging
from datetime import date
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PositiveInt, ValidationError

from greenhouse_sim.scenarios.catalogue import ScenarioRefused, Scenarios, config_digest
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import CannotCopy, Installation, scenario_installation
from greenhouse_sim.scenarios.scenario_files import (
    Recording,
    ScenarioFileError,
    export_scenario_file,
    holds_an_installation,
    import_scenario_file,
)
from greenhouse_sim.services.builder import Assessed, assess
from greenhouse_sim.services.errors import (
    Conflict,
    InvalidRequest,
    NotFound,
    ServiceError,
    first_reason,
)
from greenhouse_sim.services.run_store import ObjectStore, StoreCorrupt
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    ScenarioSummary,
    scenario,
    scenario_summary,
)
from greenhouse_sim.weather.recorded import RecordedWeather, checked_recording
from greenhouse_sim.world.site import Site

if TYPE_CHECKING:
    # Typed only: the simulator restores the files it was given at its start.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

# Where in the run store the files are kept, by the digest that names them.
KEPT_FOLDER: Final = "scenarios/"
FILE_SUFFIX: Final = ".json"
# What a scenario's file is called when it is downloaded.
DOWNLOAD_SUFFIX: Final = ".scenario.json"


class ScenarioDownload(BaseModel):
    """A scenario's file, for a client to offer as a download."""

    model_config = ConfigDict(frozen=True)

    file_name: str
    text: str
    # Whether the file carries the recorded weather its scenario runs under.
    has_recording: bool


class MissingWeather(BaseModel):
    """A recorded weather a file names and does not carry: its file name and
    the digest of the content it must have."""

    model_config = ConfigDict(frozen=True)

    file: str
    digest: str


class RunSettings(BaseModel):
    """What a scenario file holds of a run besides its house, as the scenario
    holds it: the file's contract, whose ranges are the scenario's own. The
    weather is `default`, the scenario's own; a draft's run
    (`services.drafts.DraftRun`) limits some of these further, and refuses
    them when it is asked."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    name: str
    description: str
    start_date: date
    duration_days: PositiveInt
    random_seed: NonNegativeInt
    site: Site
    weather: str = DEFAULT_WEATHER


class ScenarioUploaded(BaseModel):
    """What an upload answers: the scenario as the list shows it (none if
    its weather is missing, which stops it being registered), its house as an
    installation and its run settings, for the setup builder to open; and
    whether the file was kept."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["scenario"] = "scenario"
    file_digest: str
    scenario: ScenarioSummary | None
    kept: bool
    installation: Installation
    settings: RunSettings
    missing_weather: MissingWeather | None


class InstallationUploaded(BaseModel):
    """What an upload of an installation's file answers: the house, assessed
    as the builder's import has it. Nothing was registered or kept."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["installation"] = "installation"
    assessed: Assessed


def download(simulator: Simulator, scenario_id: str, with_recording: bool) -> ScenarioDownload:
    """A scenario's file, with its recorded weather carried unless
    `with_recording` is false. Not found if the simulator does not know the
    scenario; refused if it cannot be written as a file."""
    config = scenario(simulator.catalogue, scenario_id)
    text = _written(config, with_recording=with_recording)
    carried = with_recording and isinstance(config.weather, RecordedWeather)
    return ScenarioDownload(
        file_name=f"{scenario_id}{DOWNLOAD_SUFFIX}", text=text, has_recording=carried
    )


def upload(simulator: Simulator, text: str) -> ScenarioUploaded | InstallationUploaded:
    """A scenario file validated, registered and, if the simulator has a run
    store, kept, or an installation's file read. The same scenario file again
    is the scenario already registered. Refused (400) if it is neither kind of
    file or not a good one of its kind, naming each field at fault; a conflict
    (409) if its scenario's identifier is a packaged scenario's or another's
    registered."""
    try:
        is_installation = holds_an_installation(text)
    except ScenarioFileError as error:
        raise InvalidRequest(
            f"not a scenario file or a house file: {error.message}",
            [(error.field, error.message)],
        ) from None
    if is_installation:
        return InstallationUploaded(assessed=assess(text))
    uploaded = _registered(simulator, text)
    if uploaded.scenario is None or simulator.runs is None:
        return uploaded
    simulator.runs.put(kept_name(uploaded.file_digest), text.encode())
    return uploaded.model_copy(update={"kept": True})


def carry(catalogue: Scenarios, objects: ObjectStore, scenario_id: str) -> str | None:
    """The digest of a scenario's file, written into `objects` for an epoch of
    it to name, with its recording inside; none for a packaged scenario, which
    every simulator has. Refused if the scenario cannot be written as a file,
    or would not read back as the same scenario: a worker would run another."""
    config = scenario(catalogue, scenario_id)
    entry = catalogue.entry(scenario_id)
    if entry is not None and entry.packaged:
        return None
    text = _written(config, with_recording=True)
    try:
        read = import_scenario_file(text)
    except ScenarioFileError as error:
        raise InvalidRequest(str(error), [(error.field, error.message)]) from None
    if config_digest(read.config) != config_digest(config):
        raise InvalidRequest(f"{scenario_id!r} does not read back from its file as it is")
    name = kept_name(read.digest)
    if objects.size(name) is None:
        objects.put(name, text.encode())
    return read.digest


def take_up(simulator: Simulator, objects: ObjectStore, digest: str) -> None:
    """Registers the scenario of a file an epoch names, for a worker with no
    other way to know it. Refused if the file is gone or is not that file."""
    data = objects.get(kept_name(digest))
    if data is None:
        raise StoreCorrupt(f"the scenario file {digest} an epoch names is gone")
    if _registered(simulator, data.decode()).file_digest != digest:
        raise StoreCorrupt(f"the scenario file {digest} an epoch names is not what it says")


def kept_name(digest: str) -> str:
    """Where in the run store the file of this digest is kept."""
    return f"{KEPT_FOLDER}{digest}{FILE_SUFFIX}"


def _written(config: ScenarioConfig, *, with_recording: bool) -> str:
    """A scenario's file, as a service refuses one that cannot be written."""
    try:
        return export_scenario_file(config, with_recording=with_recording)
    except ScenarioFileError as error:
        raise InvalidRequest(str(error), [(error.field, error.message)]) from None
    except FileNotFoundError as error:
        raise NotFound(f"{config.greenhouse_id!r}: {error}") from None


def restore(simulator: Simulator) -> int:
    """The scenarios of the files kept beside the run store, registered
    again; how many were. A file whose recording another file carries waits
    until that one is registered, whatever order the store lists them in;
    one that can no longer be read or registered is left where it is and
    logged."""
    if simulator.runs is None:
        return 0
    waiting = simulator.runs.names(KEPT_FOLDER)
    restored = 0
    while waiting:
        deferred = []
        for name in waiting:
            registered = _restored(simulator, name)
            restored += registered is True
            if registered is None:
                deferred.append(name)
        if len(deferred) == len(waiting):
            for name in deferred:
                _not_restored(name, "its recorded weather is not here")
            break
        waiting = deferred
    return restored


def _restored(simulator: Simulator, name: str) -> bool | None:
    """Whether the kept file `name` was registered; None if it waits for a
    recording."""
    assert simulator.runs is not None
    try:
        data = simulator.runs.get(name)
        if data is None:
            raise NotFound(f"{name} is gone")
        return None if _registered(simulator, data.decode()).scenario is None else True
    except (ServiceError, UnicodeDecodeError) as error:
        _not_restored(name, getattr(error, "message", str(error)))
        return False


def _not_restored(name: str, why: str) -> None:
    logger.warning(
        "scenario files: %s not restored: %s",
        name,
        why,
        extra={"event": "not_restored", "label": name},
    )


def _registered(simulator: Simulator, text: str) -> ScenarioUploaded:
    try:
        read = import_scenario_file(text)
    except ScenarioFileError as error:
        raise InvalidRequest(str(error), [(error.field, error.message)]) from None
    config, recording = read.config, read.recording
    missing = None
    if read.needs_recording and recording is not None:
        found = _carried_elsewhere(simulator, recording)
        if found is None:
            missing = MissingWeather(file=recording.file, digest=recording.digest)
        else:
            config = config.model_copy(update={"weather": found})
    try:
        house = scenario_installation(config)
    except CannotCopy as error:
        raise InvalidRequest(f"not a scenario file: {error}") from None
    except ValidationError as error:
        raise InvalidRequest(f"not a scenario file: {first_reason(error)}") from None
    summary = None
    if missing is None:
        try:
            simulator.catalogue.register(config)
        except ScenarioRefused as error:
            raise Conflict(str(error)) from None
        summary = scenario_summary(simulator.catalogue, config.greenhouse_id)
        logger.info(
            "scenario files: %s registered",
            config.greenhouse_id,
            extra={"event": "registered", "label": config.greenhouse_id},
        )
    return ScenarioUploaded(
        file_digest=read.digest,
        scenario=summary,
        kept=False,
        installation=house,
        settings=_settings(config),
        missing_weather=missing,
    )


def _settings(config: ScenarioConfig) -> RunSettings:
    return RunSettings(
        scenario_id=config.greenhouse_id,
        name=config.name,
        description=config.description,
        start_date=config.start_date,
        duration_days=config.duration_days,
        random_seed=config.random_seed,
        site=config.site,
    )


def _carried_elsewhere(simulator: Simulator, recording: Recording) -> RecordedWeather | None:
    """The weather that carries the recording a file names and does not
    carry, as another scenario this simulator knows carries it: the same
    content, under the name the file gives it."""
    for scenario_id in simulator.catalogue.ids():
        entry = simulator.catalogue.entry(scenario_id)
        weather = None if entry is None else entry.config.weather
        if (
            isinstance(weather, RecordedWeather)
            and weather.text is not None
            and weather.identity() == recording.digest
        ):
            return checked_recording(recording.file, weather.content())
    return None
