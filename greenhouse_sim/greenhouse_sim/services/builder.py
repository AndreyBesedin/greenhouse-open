"""What the setup builder asks of the simulator besides its drafts (P12.2,
decision 0050): a first draft from its first form's values, a scenario's
house to start from, what stops an installation running as it is being
edited, before it is saved, and the scene of its house, to preview it as
the simulator would draw it.

Each takes an installation as its file is written (`builder.portable`) and
answers with it read, so that an editor sends back what it is given.
"""

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.installation import Finding, assess_installation
from greenhouse_sim.builder.portable import InstallationFileError, import_installation
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.installation import (
    CannotCopy,
    Installation,
    scenario_installation,
)
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION
from greenhouse_sim.scene.snapshot import SceneSnapshot, greenhouse_scene
from greenhouse_sim.services.errors import InvalidRequest, every_reason, first_reason
from greenhouse_sim.services.scenarios import scenario


class Assessed(BaseModel):
    """An installation, the format a file of it is written in, and what
    stops it running, or what it lacks."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    installation: Installation
    findings: list[Finding]


def basic(values: JsonValue) -> Assessed:
    """The draft the builder's first form describes (`BasicSetup`): a house
    of equal spans and bays and parallel rows of one crop, assessed.
    Refused, by the field at fault, if the values are not the form's or no
    greenhouse can have them."""
    try:
        form = BasicSetup.model_validate(values)
    except ValidationError as error:
        raise InvalidRequest(
            f"not the first form's values: {first_reason(error)}", every_reason(error)
        ) from None
    try:
        installation = basic_installation(form)
    except ValidationError as error:
        # What the form's own checks did not foresee, in the house's terms.
        raise InvalidRequest(f"no greenhouse has these values: {first_reason(error)}") from None
    return _assessed(installation)


def scenario_house(catalogue: Scenarios, scenario_id: str) -> Assessed:
    """A scenario's house as an installation, assessed, named as the
    scenario is, for the builder to copy: the scenario itself is never
    changed. Not found if there is no such scenario, and refused if its
    house is not one an installation holds as it is."""
    try:
        installation = scenario_installation(scenario(catalogue, scenario_id))
    except CannotCopy as reason:
        raise InvalidRequest(str(reason)) from None
    return _assessed(installation)


def assess(file: str) -> Assessed:
    """An installation's file, read and assessed as it stands."""
    return _assessed(_read(file))


def scene(file: str) -> SceneSnapshot:
    """The house an installation's file describes, as the viewer draws a
    scenario's before its crop is planted: its envelope, its rows'
    positions and supports, its fixtures and its equipment, all off."""
    installation = _read(file)
    return greenhouse_scene(
        installation.installation_id, installation.envelope, layout=installation.layout
    )


def refused_file(error: InstallationFileError) -> InvalidRequest:
    """A file refused as the client's request: its first problem, and each
    of them by its field."""
    return InvalidRequest(
        str(error), [(problem.field, problem.message) for problem in error.problems]
    )


def _read(file: str) -> Installation:
    try:
        return import_installation(file)
    except InstallationFileError as error:
        raise refused_file(error) from None


def _assessed(installation: Installation) -> Assessed:
    return Assessed(installation=installation, findings=assess_installation(installation))
