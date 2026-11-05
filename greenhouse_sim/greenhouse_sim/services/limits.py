"""What a simulator lets its runs use (decision 0067): `Limits`, given to it as its
authorisation is, from a file or the server's options, with defaults for one machine.

| Limit | Past it | By default |
| --- | --- | --- |
| Workers at once | A run waits | 2 |
| Runs waiting | Refused when asked for | 200 |
| Free disk before a run begins | Refused when asked for | 2 GB |
| Bytes of the store | Refused when asked for | None |

Each simulator has its own, so that a party's are the limits of its instance (rule 3).
A refusal says which limit it is and the figures, in words a client can show.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from greenhouse_sim.services.errors import InvalidRequest, every_reason, first_reason

DEFAULT_WORKERS: Final = 2
DEFAULT_WAITING_RUNS: Final = 200
GIGABYTE: Final = 10**9
DEFAULT_FREE_DISK_BYTES: Final = 2 * GIGABYTE
_UNITS: Final = ((GIGABYTE, "GB"), (10**6, "MB"), (10**3, "kB"))
# How an option says there is to be no limit at all.
NO_LIMIT: Final = "none"


class Limits(BaseModel):
    """A simulator's limits; none is no limit. All are optional in a file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workers: int = Field(
        DEFAULT_WORKERS, ge=1, description="how many runs its workers compute at once"
    )
    waiting_runs: int | None = Field(
        DEFAULT_WAITING_RUNS, ge=0, description="how many runs may wait for a worker"
    )
    free_disk_bytes: int | None = Field(
        DEFAULT_FREE_DISK_BYTES,
        ge=0,
        description="the bytes that must be free on the run store's disk for a run to begin",
    )
    store_bytes: int | None = Field(
        None, ge=0, description="the bytes the run store may hold for a run to begin"
    )


def in_words(size: int | float) -> str:
    """A number of bytes as a person reads it."""
    for unit, name in _UNITS:
        if size >= unit:
            return f"{size / unit:.1f} {name}"
    return f"{size:.0f} B"


def _runs(count: int) -> str:
    return "1 run" if count == 1 else f"{count} runs"


def too_many_waiting(waiting: int, limit: int) -> str:
    """Why a run that would wait is refused."""
    if limit == 0:
        return "this simulator lets no run wait for a worker, and every worker is busy"
    return (
        f"{_runs(waiting)} waiting for a worker, and this simulator lets {_runs(limit)} wait: "
        "ask again once some have begun, or raise that limit"
    )


def too_little_disk(free: int, floor: int) -> str:
    """Why a run is refused on a disk that is nearly full."""
    return (
        f"the disk of the run store has {in_words(free)} free, and a run begins only with "
        f"{in_words(floor)} free: free some space, or lower that limit"
    )


def store_too_large(held: int, limit: int) -> str:
    """Why a run is refused on a store that holds what it may."""
    return (
        f"the run store holds {in_words(held)}, and a run begins only under {in_words(limit)}: "
        "delete some runs, or raise that limit"
    )


def _in_file(path: Path) -> dict[str, Any]:
    try:
        given = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InvalidRequest(f"no limits read from {path}: {error}") from None
    if not isinstance(given, dict):
        raise InvalidRequest(f"not limits in {path}: it is to be a JSON object")
    return given


def limits_given(
    path: Path | None = None, options: Mapping[str, str | None] | None = None
) -> Limits:
    """The limits of a file, as JSON of `Limits`, each option given taking the place of
    what it says of the same limit, `NO_LIMIT` for none; the defaults for the rest.
    Refused, saying why, if the file cannot be read or either says what is not one."""
    named = {
        name: None if value == NO_LIMIT else value
        for name, value in (options or {}).items()
        if value is not None
    }
    given = {} if path is None else _in_file(path)
    try:
        return Limits.model_validate(given | named)
    except ValidationError as error:
        where = "the options" if path is None else f"{path} and the options"
        raise InvalidRequest(
            f"not limits in {where}: {first_reason(error)}", every_reason(error)
        ) from None
