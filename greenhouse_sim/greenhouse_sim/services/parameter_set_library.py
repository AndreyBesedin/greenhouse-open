"""A simulator's crop parameter sets, kept and served (P20.4, decision
0077): a model's sets listed, one read, saved, compared with another,
downloaded as its file and uploaded from one.

- **Listed and read:** its model's published set first, then those kept in
  the run store (`parameter_sets.kept_sets`), by name and version, each with
  its digest; a set read gives every value it resolves to besides those it
  changes.
- **Saved** (`save`): a set's file without its version, which takes its
  name's next. Saved with the numbers a version of its name already has, it
  is that version, and nothing is written; a version once written is never
  changed (`parameter_sets.keep`).
- **Uploaded** (`upload`): a set's file, as one is downloaded, kept under its
  own name and version, and refused if those are kept with other numbers.
- **Compared** (`compare`): two sets of one model, parameter by parameter.

A published set's name is its model's: no set is saved or uploaded under it
but the published set itself. A value outside its range, a fixed one changed
and a base that is not known are refused by field. A simulator without a run
store keeps no sets: it lists and serves its published ones.
"""

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.biology.parameter_sets import (
    FIRST_VERSION,
    PARAMETER_MODELS,
    PUBLISHED_NAMES,
    PUBLISHED_SETS,
    InvalidParameterSet,
    ParameterChange,
    ParameterSet,
    ResolvedSet,
    SetKey,
    SetNamed,
    compared,
    read_parameter_set,
    resolved,
    set_key,
)
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.parameter_sets import keep, kept_sets
from greenhouse_sim.services.run_store import ObjectStore

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# The largest set's file an upload reads: a set of every parameter, with
# why each, is some ten kilobytes.
MAX_SET_BYTES: Final = 1_000_000
# How many times a save takes its name's next version again when another
# save took it first.
SAVE_ATTEMPTS: Final = 8
# What a set's file is called when it is downloaded.
DOWNLOAD_SUFFIX: Final = ".parameter_set.json"
# The indent a downloaded file is written with, for a person to read.
FILE_INDENT: Final = 2


class SetListed(BaseModel):
    """A set as a model's list shows it: its model, name and version, its
    digest, what it is based on, the model version and cultivar it was made
    for, its description, and whether it is its model's published set."""

    model_config = ConfigDict(frozen=True)

    model: str
    name: str
    version: int
    digest: str
    based_on: SetNamed | None
    made_for: int
    cultivar: str | None
    description: str
    published: bool


class SetRead(SetListed):
    """A set as it is read: as listed, with the values it changes from its
    base and why each, and every value it resolves to, by its model's
    parameters' fields."""

    parameters: dict[str, float]
    why: dict[str, str]
    values: dict[str, float]


class SetComparison(BaseModel):
    """Two sets of one model, by name, version and digest, and each
    parameter they give apart, in their model's order."""

    model_config = ConfigDict(frozen=True)

    first: SetNamed
    second: SetNamed
    changes: list[ParameterChange]


class SetDownload(BaseModel):
    """A set's file, for a client to offer as a download."""

    model_config = ConfigDict(frozen=True)

    file_name: str
    text: str


def model_sets(simulator: Simulator, model: str) -> list[SetListed]:
    """A model's sets: its published set, then those kept, by name and
    version. Not found for a model that has no sets."""
    _checked_model(model)
    known = kept_sets(simulator.runs)
    sets = [PUBLISHED_SETS[model], *(known[key] for key in sorted(known) if key[0] == model)]
    return [_listed(_resolved(each, known)) for each in sets]


def parameter_set(simulator: Simulator, model: str, name: str, version: int) -> SetRead:
    """One of a model's sets, with every value it resolves to; not found if
    the simulator has none of that name and version."""
    found = _resolved(*_found(simulator, (model, name, version)))
    return SetRead(
        **_listed(found).model_dump(),
        parameters=found.parameter_set.parameters,
        why=found.parameter_set.why,
        values=found.values.model_dump(),
    )


def compare(simulator: Simulator, first: SetKey, second: SetKey) -> SetComparison:
    """Two sets of one model, compared parameter by parameter; not found if
    either is not the simulator's."""
    if first[0] != second[0]:
        raise InvalidRequest(f"{first[0]} and {second[0]} are sets of different models")
    one, other = _resolved(*_found(simulator, first)), _resolved(*_found(simulator, second))
    return SetComparison(first=one.named, second=other.named, changes=compared(one, other))


def download(simulator: Simulator, model: str, name: str, version: int) -> SetDownload:
    """A set's file, as `upload` reads it back."""
    found, _ = _found(simulator, (model, name, version))
    return SetDownload(
        file_name=f"{model}.{name}.v{version}{DOWNLOAD_SUFFIX}",
        text=found.model_dump_json(indent=FILE_INDENT) + "\n",
    )


def save(simulator: Simulator, model: str, document: JsonValue) -> SetListed:
    """A set's file without its version, kept under its name's next version,
    or answered as the version of its name that has its numbers. Refused, by
    field, if it is not a set of `model`, names a version or is named as a
    published set; not found without a run store."""
    _checked_model(model)
    objects = _store(simulator)
    if not isinstance(document, dict):
        raise InvalidRequest("a parameter set's file is a JSON object")
    if "version" in document:
        raise InvalidRequest(
            "a saved set takes its name's next version",
            [("version", "a save names none: upload a set's file to keep its own")],
        )
    if document.get("model") != model:
        raise InvalidRequest(
            f"a set of {model} is saved here", [("model", f"a set of {model}, not another's")]
        )
    _not_published_name(model, document.get("name"))
    for _ in range(SAVE_ATTEMPTS):
        known = kept_sets(objects)
        first = _read(document | {"version": FIRST_VERSION}, known)
        versions = sorted(key[2] for key in known if key[:2] == set_key(first.parameter_set)[:2])
        for version in versions:
            same = known[(model, first.parameter_set.name, version)]
            if _resolved(same, known).digest == first.digest:
                return _listed(_resolved(same, known))
        following = (versions[-1] + 1) if versions else FIRST_VERSION
        try:
            return _listed(keep(objects, document | {"version": following}))
        except Conflict:
            # Another save took that version first: take the next again.
            continue
    raise Conflict(f"{document.get('name')!r} is being saved by others: save it again")


def upload(simulator: Simulator, text: str) -> SetListed:
    """A set's file, as one is downloaded, kept under its own name and
    version, or answered as the version kept with its numbers. Refused, by
    field, if it is not a set, or is named as a published set and is not it;
    a conflict if its name and version are kept with other numbers; not found
    without a run store."""
    objects = _store(simulator)
    if len(text.encode("utf-8")) > MAX_SET_BYTES:
        raise InvalidRequest(f"a parameter set's file is at most {MAX_SET_BYTES} bytes")
    try:
        document = json.loads(text)
    except ValueError:
        raise InvalidRequest("a parameter set's file is JSON") from None
    if not isinstance(document, dict):
        raise InvalidRequest("a parameter set's file is a JSON object")
    read = _read(document, kept_sets(objects)).parameter_set
    if set_key(read) != set_key(PUBLISHED_SETS[read.model]):
        _not_published_name(read.model, read.name)
    return _listed(keep(objects, document))


def _store(simulator: Simulator) -> ObjectStore:
    if simulator.runs is None:
        raise NotFound("this simulator keeps no parameter sets: it was made with no run store")
    return simulator.runs


def _checked_model(model: str) -> None:
    if model not in PARAMETER_MODELS:
        raise NotFound(
            f"{model!r} has no parameter sets: those that have are {', '.join(PARAMETER_MODELS)}"
        )


def _found(simulator: Simulator, key: SetKey) -> tuple[ParameterSet, dict[SetKey, ParameterSet]]:
    """The set of a model, name and version, published or kept, and those
    kept, which it may be based on."""
    model, name, version = key
    _checked_model(model)
    known = kept_sets(simulator.runs)
    published = PUBLISHED_SETS[model]
    found = published if set_key(published) == key else known.get(key)
    if found is None:
        raise NotFound(f"no parameter set {name} v{version} of {model} is kept")
    return found, known


def _resolved(parameter_set: ParameterSet, known: Mapping[SetKey, ParameterSet]) -> ResolvedSet:
    try:
        return resolved(parameter_set, known)
    except InvalidParameterSet as error:
        raise Conflict(f"the kept set {parameter_set.name} no longer resolves: {error}") from None


def _read(document: Mapping[str, JsonValue], known: Mapping[SetKey, ParameterSet]) -> ResolvedSet:
    """A set's file, read and resolved, or refused by field."""
    try:
        return resolved(read_parameter_set(document), known)
    except InvalidParameterSet as error:
        raise InvalidRequest(str(error), list(error.problems.items())) from None


def _not_published_name(model: str, name: JsonValue) -> None:
    published = PUBLISHED_NAMES[model]
    if name == published:
        raise InvalidRequest(
            f"{published} is the name of {model}'s published set",
            [("name", f"{published} is the published set's: name a set of your own otherwise")],
        )


def _listed(found: ResolvedSet) -> SetListed:
    each = found.parameter_set
    return SetListed(
        model=each.model,
        name=each.name,
        version=each.version,
        digest=found.digest,
        based_on=each.based_on,
        made_for=each.made_for,
        cultivar=each.cultivar,
        description=each.description,
        published=set_key(each) == set_key(PUBLISHED_SETS[each.model]),
    )
