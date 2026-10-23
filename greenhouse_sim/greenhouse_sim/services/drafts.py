"""The installations' drafts a simulator is given a store of, and their runs
(P12.1, decisions 0050 and 0051).

A draft is kept revision by revision (`builder.drafts`); each answer about
one says what stops it running (`builder.installation.assess_installation`).
A change names the revision it was made on, and is refused as a conflict if
another was saved since.

A draft runs as a scenario of its own: its installation, at a revision,
with what a scenario adds to a house, a period, a site, a seed and a
weather, registered with the simulator (decision 0048). It is then listed,
drawn and run as any scenario is, by its identifier, until the simulator
closes. A draft that the assessment says cannot run is refused, with each
reason.
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
)

from greenhouse_sim.builder.drafts import (
    DraftNotFound,
    DraftStoreError,
    Revision,
    StaleDraft,
)
from greenhouse_sim.builder.drafts import DraftStore as DraftStore
from greenhouse_sim.builder.installation import Finding, assess_installation
from greenhouse_sim.builder.portable import InstallationFileError, import_installation
from greenhouse_sim.scenarios.catalogue import SCENARIO_ID, ScenarioRefused
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import CannotRun, Installation, scenario_house
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, first_reason
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    ScenarioSummary,
    scenario_summary,
    with_weather,
)
from greenhouse_sim.world.site import DEFAULT_SITE, Site

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

# The most days a draft's run lasts: a year and a day.
MOST_DAYS: Final = 366
# The days a draft's run may start on: those whose suns and weathers the
# simulator works out, well within what a date can hold.
EARLIEST_START: Final = date(1900, 1, 1)
LATEST_START: Final = date(2199, 12, 31)
# What of a draft's identifier a scenario's cannot have, which its run's
# name writes as `_`.
_NOT_IN_A_SCENARIO_ID: Final = re.compile(r"[^a-z0-9_]")


class DraftAnswer(BaseModel):
    """A draft at a revision, as an editor opens it: its installation, the
    format a file of it is written in, and what stops it running, or what it
    lacks."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    revision: int
    saved_at: datetime
    schema_version: int = SCHEMA_VERSION
    installation: Installation
    findings: list[Finding]


class DraftListed(BaseModel):
    """A draft as a list of them shows it: its latest revision."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    name: str
    revision: int
    saved_at: datetime


class RevisionListed(BaseModel):
    """A revision of a draft as a list of them shows it."""

    model_config = ConfigDict(frozen=True)

    revision: int
    saved_at: datetime
    name: str


class DraftRun(BaseModel):
    """What a draft's run adds to its installation: a scenario's own fields.
    It is named `<draft>_r<revision>`, in lower case with `_` for what a
    scenario's name cannot hold, unless it is given a name; the rest is as
    a scenario's defaults are."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: Annotated[str, Field(pattern=f"^{SCENARIO_ID.pattern}$")] | None = None
    name: Annotated[str, Field(min_length=1)] | None = None
    description: str = ""
    start_date: Annotated[date, Field(ge=EARLIEST_START, le=LATEST_START)]
    duration_days: Annotated[PositiveInt, Field(le=MOST_DAYS)]
    random_seed: NonNegativeInt = 0
    site: Site = DEFAULT_SITE
    # A preset or recorded weather by name, as a run's is chosen, or the
    # default scenario's own.
    weather: str = DEFAULT_WEATHER


def store_at(path: Path) -> DraftStore:
    """The drafts kept in the file at `path`, made with its folder if it is
    missing, for a simulator to be given. Refused if the file is not a
    store of drafts, or cannot be made or opened."""
    try:
        return DraftStore(path)
    except (DraftStoreError, OSError) as error:
        raise InvalidRequest(f"{path}: drafts cannot be kept there: {error}") from None


def drafts(simulator: Simulator) -> list[DraftListed]:
    """Every draft kept, by its identifier."""
    return [
        DraftListed(
            draft_id=draft.draft_id,
            name=draft.name,
            revision=draft.revision,
            saved_at=draft.saved_at,
        )
        for draft in _store(simulator).drafts()
    ]


def draft(simulator: Simulator, draft_id: str, revision: int | None = None) -> DraftAnswer:
    """A draft at a revision, by default its latest."""
    return _answer(_opened(_store(simulator), draft_id, revision))


def revisions(simulator: Simulator, draft_id: str) -> list[RevisionListed]:
    """Every revision of a draft, the first first."""
    try:
        kept = _store(simulator).revisions(draft_id)
    except DraftNotFound as error:
        raise NotFound(str(error)) from None
    return [
        RevisionListed(revision=each.revision, saved_at=each.saved_at, name=each.name)
        for each in kept
    ]


def save(simulator: Simulator, draft_id: str, file: str, on: int | None) -> DraftAnswer:
    """An installation's file saved as a draft's next revision, made on
    revision `on`, or as a new draft if None. Refused if the file is not an
    installation, or one of another draft, and as a conflict if `on` is no
    longer the draft's latest revision."""
    try:
        installation = import_installation(file)
    except InstallationFileError as error:
        raise InvalidRequest(str(error)) from None
    if installation.installation_id != draft_id:
        raise InvalidRequest(
            f"the file holds the installation {installation.installation_id!r}, "
            f"not the draft {draft_id!r}"
        )
    try:
        saved = _store(simulator).save(installation, on=on)
    except StaleDraft as error:
        raise Conflict(str(error)) from None
    except InstallationFileError as error:
        # As the store writes it, the file may not be read back.
        raise InvalidRequest(str(error)) from None
    logger.info(
        "drafts: saved %s, revision %d",
        draft_id,
        saved.revision,
        extra={"event": "saved", "label": draft_id},
    )
    return _answer(saved)


def revert(simulator: Simulator, draft_id: str, revision: int, on: int) -> DraftAnswer:
    """A draft's earlier revision saved again as its latest, made on
    revision `on`."""
    try:
        saved = _store(simulator).revert(draft_id, revision, on=on)
    except DraftNotFound as error:
        raise NotFound(str(error)) from None
    except StaleDraft as error:
        raise Conflict(str(error)) from None
    except InstallationFileError as error:
        raise Conflict(_unreadable(draft_id, revision, error)) from None
    logger.info(
        "drafts: reverted %s to revision %d, as revision %d",
        draft_id,
        revision,
        saved.revision,
        extra={"event": "reverted", "label": draft_id},
    )
    return _answer(saved)


def delete(simulator: Simulator, draft_id: str, on: int) -> dict[str, JsonValue]:
    """A draft forgotten with its revisions, made on revision `on`."""
    try:
        _store(simulator).delete(draft_id, on=on)
    except DraftNotFound as error:
        raise NotFound(str(error)) from None
    except StaleDraft as error:
        raise Conflict(str(error)) from None
    logger.info("drafts: deleted %s", draft_id, extra={"event": "deleted", "label": draft_id})
    return {"deleted": draft_id}


def run(
    simulator: Simulator, draft_id: str, revision: int | None, settings: JsonValue
) -> ScenarioSummary:
    """A draft at a revision, by default its latest, run as a scenario with
    `settings` (`DraftRun`), registered with the simulator and answered as
    the scenario list shows it. Asked again the same, it is the scenario
    already registered. Refused if the draft cannot run, saying why, or if
    the settings are not a run's; and as a conflict if its scenario's name
    is a packaged scenario's, or another's registered."""
    kept = _opened(_store(simulator), draft_id, revision)
    errors = [
        found for found in assess_installation(kept.installation) if found.severity == "error"
    ]
    if errors:
        reasons = " ".join(found.message for found in errors)
        raise InvalidRequest(
            f"draft {draft_id!r} at revision {kept.revision} cannot run: {reasons}"
        )
    try:
        asked = DraftRun.model_validate(settings)
    except ValidationError as error:
        raise InvalidRequest(f"not a draft's run: {first_reason(error)}") from None
    try:
        house = scenario_house(kept.installation)
        own = _NOT_IN_A_SCENARIO_ID.sub("_", f"{draft_id.lower()}_r{kept.revision}")
        config = ScenarioConfig.model_validate(
            {
                "greenhouse_id": asked.scenario_id or own,
                "name": asked.name or kept.installation.name,
                "description": asked.description,
                "start_date": asked.start_date,
                "duration_days": asked.duration_days,
                "random_seed": asked.random_seed,
                "site": asked.site,
            }
            | dict(house)
        )
    except CannotRun as error:
        raise InvalidRequest(f"draft {draft_id!r} cannot run: {error}") from None
    except ValidationError as error:
        raise InvalidRequest(f"draft {draft_id!r} cannot run: {first_reason(error)}") from None
    config = with_weather(config, asked.weather)
    try:
        entry = simulator.catalogue.register(config)
    except ScenarioRefused as error:
        raise Conflict(str(error)) from None
    logger.info(
        "drafts: %s, revision %d, runs as %s",
        draft_id,
        kept.revision,
        entry.scenario_id,
        extra={"event": "registered", "label": entry.scenario_id},
    )
    return scenario_summary(simulator.catalogue, entry.scenario_id)


def _store(simulator: Simulator) -> DraftStore:
    if simulator.drafts is None:
        raise NotFound("this simulator keeps no drafts: start it with a store of them (--drafts)")
    return simulator.drafts


def _opened(store: DraftStore, draft_id: str, revision: int | None) -> Revision:
    try:
        return store.open(draft_id, revision)
    except DraftNotFound as error:
        raise NotFound(str(error)) from None
    except InstallationFileError as error:
        raise Conflict(_unreadable(draft_id, revision, error)) from None


def _unreadable(draft_id: str, revision: int | None, error: InstallationFileError) -> str:
    """Why a revision kept cannot be read, as by one a later simulator saved
    in a format this one does not read."""
    which = "its latest revision" if revision is None else f"revision {revision}"
    return f"draft {draft_id!r}: {which} is kept as a file this simulator cannot read: {error}"


def _answer(kept: Revision) -> DraftAnswer:
    return DraftAnswer(
        draft_id=kept.draft_id,
        revision=kept.revision,
        saved_at=kept.saved_at,
        installation=kept.installation,
        findings=assess_installation(kept.installation),
    )
