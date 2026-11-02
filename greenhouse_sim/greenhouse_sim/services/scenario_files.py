"""A scenario as a file: downloaded, and uploaded, registered and kept
(P17.11).

An upload validates the file (`greenhouse_sim.scenarios.scenario_files`),
registers its scenario as a draft's run is (decision 0048) and, with a run
store, keeps the file beside it, so that a simulator started on the store
registers the scenario again. It never starts a run: it answers the house and
the run settings, for the setup builder to open. A scenario under a recorded
weather the file does not carry and this process does not offer is not
registered; the answer names the weather.
"""

import logging
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.scenarios.catalogue import ScenarioRefused
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import CannotCopy, Installation, scenario_installation
from greenhouse_sim.scenarios.scenario_files import (
    ScenarioFile,
    ScenarioFileError,
    export_scenario_file,
    import_scenario_file,
)
from greenhouse_sim.services.drafts import DraftRun
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    ScenarioSummary,
    scenario,
    scenario_summary,
)
from greenhouse_sim.weather.recorded import RecordedWeather, keep_recording

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


class ScenarioUploaded(BaseModel):
    """What an upload answers: the scenario as the list shows it (none if
    its weather is missing, which stops it being registered), its house as an
    installation and its run settings as a draft's run holds them, for the
    setup builder to open; and whether the file was kept."""

    model_config = ConfigDict(frozen=True)

    file_digest: str
    scenario: ScenarioSummary | None
    kept: bool
    installation: Installation
    settings: DraftRun
    missing_weather: MissingWeather | None


def download(simulator: Simulator, scenario_id: str, with_recording: bool) -> ScenarioDownload:
    """A scenario's file, with its recorded weather carried unless
    `with_recording` is false. Not found if the simulator does not know the
    scenario; refused if it cannot be written as a file."""
    config = scenario(simulator.catalogue, scenario_id)
    try:
        text = export_scenario_file(config, with_recording=with_recording)
    except ScenarioFileError as error:
        raise InvalidRequest(str(error), [(error.field, error.message)]) from None
    except FileNotFoundError as error:
        raise NotFound(f"{scenario_id!r}: {error}") from None
    carried = with_recording and isinstance(config.weather, RecordedWeather)
    return ScenarioDownload(
        file_name=f"{scenario_id}{DOWNLOAD_SUFFIX}", text=text, has_recording=carried
    )


def upload(simulator: Simulator, text: str) -> ScenarioUploaded:
    """A scenario file validated, registered and, if the simulator has a run
    store, kept. The same file again is the scenario already registered.
    Refused (400) if it is not a scenario file, naming each field at fault;
    a conflict (409) if its scenario's identifier is a packaged scenario's or
    another's registered."""
    uploaded = _registered(simulator, text)
    if uploaded.scenario is None or simulator.runs is None:
        return uploaded
    simulator.runs.put(f"{KEPT_FOLDER}{uploaded.file_digest}{FILE_SUFFIX}", text.encode())
    return uploaded.model_copy(update={"kept": True})


def restore(simulator: Simulator) -> int:
    """The scenarios of the files kept beside the run store, registered
    again; how many were. A file that can no longer be read or registered is
    left where it is and logged."""
    if simulator.runs is None:
        return 0
    restored = 0
    for name in simulator.runs.names(KEPT_FOLDER):
        data = simulator.runs.get(name)
        try:
            if data is None:
                raise NotFound(f"{name} is gone")
            if _registered(simulator, data.decode()).scenario is not None:
                restored += 1
        except (ServiceError, UnicodeDecodeError) as error:
            logger.warning(
                "scenario files: %s not restored: %s",
                name,
                getattr(error, "message", error),
                extra={"event": "not_restored", "label": name},
            )
    return restored


def _registered(simulator: Simulator, text: str) -> ScenarioUploaded:
    try:
        read = import_scenario_file(text)
    except ScenarioFileError as error:
        raise InvalidRequest(str(error), [(error.field, error.message)]) from None
    config = _with_its_recording(read)
    try:
        house = scenario_installation(config)
    except CannotCopy as error:
        raise InvalidRequest(f"not a scenario file: {error}") from None
    settings = DraftRun(
        scenario_id=config.greenhouse_id,
        name=config.name,
        description=config.description,
        start_date=config.start_date,
        duration_days=config.duration_days,
        random_seed=config.random_seed,
        site=config.site,
        weather=DEFAULT_WEATHER,
    )
    recording = read.recording
    missing = (
        MissingWeather(file=recording.file, digest=recording.digest)
        if read.recording_missing and recording is not None
        else None
    )
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
        settings=settings,
        missing_weather=missing,
    )


def _with_its_recording(read: ScenarioFile) -> ScenarioConfig:
    """The scenario of a file, its recorded weather, if the file carries it,
    offered with the packaged ones: under the file's name, or, if that name
    is taken by other content, under a name with the content's digest, which
    the scenario then runs under."""
    recording = read.recording
    if recording is None or recording.csv is None:
        return read.config
    kept = keep_recording(recording.file, recording.csv)
    if kept == recording.file:
        return read.config
    return read.config.model_copy(update={"weather": RecordedWeather(file=kept)})
