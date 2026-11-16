"""The crop parameter sets a simulator runs (P20.3, decision 0077): its
models' published sets, from the package, and those it keeps in its run
store.

- **Kept** (`keep`): a set's file, read, resolved against the published sets
  and those kept, and written once under its model, name and version
  (`kept_name`). The same numbers again are the version kept; other numbers
  under a name and version kept, a published one's included, are refused.
- **Looked up** (`with_parameter_set`): as a scenario is registered, the set
  its crop section names, among the published and the kept, resolved and
  carried by the section (`CarriedSet`), so that its runs grow those numbers
  whatever is kept or deleted after. A set it does not have is refused.
- **Told** (`set_identity`, `set_run`): what tells a run under a set apart,
  its digest, and nothing for its model's published set, so that a run under
  that one is named as it was; and the set as a run's manifest answer gives
  it, with the version of its model it was made for beside the model's own,
  which a run under a set made for another version is not refused for.
"""

import json
import logging
from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.biology.parameter_sets import (
    PUBLISHED_SETS,
    InvalidParameterSet,
    ParameterSet,
    ResolvedSet,
    SetKey,
    read_parameter_set,
    resolved,
    set_key,
)
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import (
    CarriedSet,
    ReducedTomgroCrop,
    VanthoorKatzinCrop,
    carried_set,
    runs_published,
)
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.run_store import ObjectStore

logger = logging.getLogger(__name__)

# Where in the run store the sets kept are, by model, name and version.
KEPT_FOLDER: Final = "parameter_sets/"


class SetRun(BaseModel):
    """The parameter set a run grows its crop with, as its manifest answer
    gives it: its name, its version and its digest, and the version of its
    model it was made for, which may be another than the one run."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    digest: str
    made_for: int


def kept_name(key: SetKey) -> str:
    """Where in the run store the set of this model, name and version is."""
    model, name, version = key
    return f"{KEPT_FOLDER}{model}/{name}/v{version}.json"


def kept_sets(objects: ObjectStore | None) -> dict[SetKey, ParameterSet]:
    """Every set kept in `objects`, by its model, name and version; none
    without a store. A file that no longer reads as a set is left out, and
    logged."""
    if objects is None:
        return {}
    found: dict[SetKey, ParameterSet] = {}
    for name in objects.names(KEPT_FOLDER):
        data = objects.get(name)
        if data is None:
            continue
        try:
            read = read_parameter_set(json.loads(data))
        except (ValueError, TypeError) as error:
            logger.warning("parameter sets: %s cannot be read: %s", name, error)
            continue
        found[set_key(read)] = read
    return found


def keep(objects: ObjectStore, document: Mapping[str, JsonValue]) -> ResolvedSet:
    """A set's file, kept in `objects` under its model, name and version
    unless that version is kept with the same numbers, and answered
    resolved. Refused, by field, if it is not a set or does not resolve; a
    conflict if its name and version are kept, or published, with other
    numbers."""
    known = kept_sets(objects)
    try:
        read = read_parameter_set(document)
        kept = resolved(read, known)
    except InvalidParameterSet as error:
        raise InvalidRequest(str(error), list(error.problems.items())) from None
    key = set_key(read)
    published = {set_key(each): each for each in PUBLISHED_SETS.values()}
    already = published.get(key) or known.get(key)
    if already is None and objects.create(kept_name(key), read.model_dump_json().encode()):
        return kept
    if already is None:
        already = read_parameter_set(json.loads(objects.get(kept_name(key)) or b"{}"))
    if resolved(already, known).digest != kept.digest:
        raise Conflict(
            f"{read.name} v{read.version} of {read.model} is kept with other numbers: a "
            "correction is a version of its own"
        )
    return kept


def with_parameter_set(
    config: ScenarioConfig, known: Mapping[SetKey, ParameterSet]
) -> ScenarioConfig:
    """`config` with the set its crop section names carried by the section,
    looked up among the published sets and `known`, and resolved; as it is
    if its crop names no set, or its model's published one. Refused if the
    set is not known or does not resolve."""
    section = config.crop
    if not isinstance(section, ReducedTomgroCrop | VanthoorKatzinCrop):
        return config
    carried: CarriedSet | None = None
    if not runs_published(section):
        key = (section.kind, section.parameter_set, section.parameter_set_version)
        found = known.get(key)
        named = f"{section.parameter_set} v{section.parameter_set_version} of {section.kind}"
        if found is None:
            raise InvalidRequest(
                f"{config.greenhouse_id!r} runs the parameter set {named}, which this "
                "simulator does not keep",
                [("crop.parameter_set", f"no set {named} is kept")],
            )
        try:
            kept = resolved(found, known)
        except InvalidParameterSet as error:
            raise InvalidRequest(f"the parameter set {named}: {error}") from None
        carried = CarriedSet(
            files=tuple(each.model_dump(mode="json") for each in _line(found, known)),
            values=kept.values.model_dump(),
            digest=kept.digest,
        )
    return config.model_copy(update={"crop": section.model_copy(update={"carried": carried})})


def set_identity(config: ScenarioConfig) -> str:
    """What tells a run under the set its crop names from another: its
    digest; nothing for a crop that names none, or names its model's
    published set, whose runs are named as they were."""
    section = config.crop
    if not isinstance(section, ReducedTomgroCrop | VanthoorKatzinCrop):
        return ""
    carried = carried_set(section)
    return "" if carried is None else carried.digest


def set_run(config: ScenarioConfig) -> SetRun | None:
    """The set a scenario's crop grows with, as its run's manifest answer
    gives it; none for a crop that names none."""
    section = config.crop
    if not isinstance(section, ReducedTomgroCrop | VanthoorKatzinCrop):
        return None
    carried = carried_set(section)
    if carried is None:
        published = PUBLISHED_SETS[section.kind]
        return SetRun(
            name=published.name,
            version=published.version,
            digest=resolved(published).digest,
            made_for=published.made_for,
        )
    return SetRun(
        name=section.parameter_set,
        version=section.parameter_set_version,
        digest=carried.digest,
        made_for=ParameterSet.model_validate(carried.files[0]).made_for,
    )


def _line(parameter_set: ParameterSet, known: Mapping[SetKey, ParameterSet]) -> list[ParameterSet]:
    """A set and each of its bases that is not published, its own first."""
    published = {set_key(each) for each in PUBLISHED_SETS.values()}
    line = [parameter_set]
    while (based_on := line[-1].based_on) is not None:
        key = (parameter_set.model, based_on.name, based_on.version)
        if key in published:
            break
        line.append(known[key])
    return line
