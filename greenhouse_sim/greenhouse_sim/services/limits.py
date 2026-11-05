"""What a simulator lets its runs use (decision 0067): `Limits`, given to it as its
authorisation is, from a file or the server's options, with defaults for one machine.

| Limit | Past it | By default |
| --- | --- | --- |
| Workers at once | A run waits | 2 |
| Runs waiting | Refused when asked for | 200 |
| Free disk before a run begins | Refused when asked for | 2 GB |
| Bytes of the store | Refused when asked for | None |
| Bytes of one epoch | Ended at its commit | None |
| Memory of one worker | Ended | Half the machine's memory, shared between the workers |
| CPU or wall time of one epoch | Ended | None |

Each simulator has its own, so that a party's are the limits of its instance (rule 3).
A refusal says which limit it is and the figures, in words a client can show.

What ends an epoch is its `Budget`, the part of the limits its worker needs. It goes
through the store, as all a worker needs does (rule 1), written when the epoch is put
in line, so that raising a limit and asking for it again gives it the new one. An epoch
is ended by its worker, and not by whoever started it, which may be on another machine
or gone.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from greenhouse_sim.services.errors import (
    InvalidRequest,
    ServiceError,
    every_reason,
    first_reason,
)
from greenhouse_sim.services.resources import machine_memory_bytes

DEFAULT_WORKERS: Final = 2
DEFAULT_WAITING_RUNS: Final = 200
GIGABYTE: Final = 10**9
DEFAULT_FREE_DISK_BYTES: Final = 2 * GIGABYTE
_UNITS: Final = ((GIGABYTE, "GB"), (10**6, "MB"), (10**3, "kB"))
# How an option says there is to be no limit at all.
NO_LIMIT: Final = "none"
# Half a machine's memory goes to its workers, and the rest to all else on it.
_SHARE_OF_THE_MACHINE: Final = 2
_CARRY_ON: Final = (
    "what it committed can be read, and it can be carried on once that limit is raised"
)
_WHOLE_SECONDS_FROM: Final = 10.0


class LimitPassed(ServiceError):
    """An epoch has passed a limit of its budget: the message says which, and the figures."""


class Budget(BaseModel):
    """What one epoch's worker may use, as the store says; none is no limit. Bytes,
    CPU and wall time are the epoch's whole, across its resumes, since a resume starts
    from what it holds and they do not come back. Memory is of each worker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch_bytes: int | None = None
    worker_memory_bytes: int | None = None
    epoch_cpu_s: float | None = None
    epoch_wall_s: float | None = None

    @property
    def needs_a_watch(self) -> bool:
        """Whether a limit can be passed between two commits."""
        return not (
            self.worker_memory_bytes is None
            and self.epoch_cpu_s is None
            and self.epoch_wall_s is None
        )

    def bytes_past(self, kept: int) -> str | None:
        """Why an epoch that keeps this much is to end, if it is."""
        limit = self.epoch_bytes
        if limit is None or kept <= limit:
            return None
        return (
            f"it kept {in_words(kept)}, past the limit of {in_words(limit)} on what one run "
            f"may keep: {_CARRY_ON}"
        )

    def memory_past(self, held: int) -> str | None:
        """Why a worker that has held this much is to end, if it is."""
        limit = self.worker_memory_bytes
        if limit is None or held <= limit:
            return None
        return (
            f"its worker held {in_words(held)} of memory, past the limit of {in_words(limit)} "
            f"on one worker: {_CARRY_ON}"
        )

    def time_past(self, *, cpu_s: float | None, wall_s: float | None) -> str | None:
        """Why an epoch that has taken this long is to end, if it is."""
        if self.epoch_cpu_s is not None and (cpu_s or 0.0) > self.epoch_cpu_s:
            return (
                f"it took {_seconds(cpu_s or 0.0)} of a core, past the limit of "
                f"{_seconds(self.epoch_cpu_s)} on one run: {_CARRY_ON}"
            )
        if self.epoch_wall_s is not None and (wall_s or 0.0) > self.epoch_wall_s:
            return (
                f"it took {_seconds(wall_s or 0.0)} from its worker's start, past the limit of "
                f"{_seconds(self.epoch_wall_s)} on one run: {_CARRY_ON}"
            )
        return None


def _memory_of_a_worker(given: dict[str, Any]) -> int:
    """Half the machine's memory, shared between the workers the limits say."""
    workers: int = given.get("workers", DEFAULT_WORKERS)
    return machine_memory_bytes() // _SHARE_OF_THE_MACHINE // workers


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
    epoch_bytes: int | None = Field(
        None, ge=0, description="the bytes one run may keep: it ends at the commit past them"
    )
    worker_memory_bytes: int | None = Field(
        default_factory=_memory_of_a_worker,
        ge=0,
        description=(
            "the bytes of memory one worker may hold: its run ends; by default half of "
            "the machine's, shared between the workers"
        ),
    )
    epoch_cpu_s: float | None = Field(
        None, ge=0, description="the seconds of a core one run may take: it ends"
    )
    epoch_wall_s: float | None = Field(
        None, ge=0, description="the seconds its workers may take over one run: it ends"
    )

    @property
    def budget(self) -> Budget:
        """The part of them a worker needs."""
        return Budget(
            epoch_bytes=self.epoch_bytes,
            worker_memory_bytes=self.worker_memory_bytes,
            epoch_cpu_s=self.epoch_cpu_s,
            epoch_wall_s=self.epoch_wall_s,
        )


def in_words(size: int | float) -> str:
    """A number of bytes as a person reads it."""
    for unit, name in _UNITS:
        if size >= unit:
            return f"{size / unit:.1f} {name}"
    return f"{size:.0f} B"


def _seconds(seconds: float) -> str:
    return f"{seconds:,.0f} s" if seconds >= _WHOLE_SECONDS_FROM else f"{seconds:.2f} s"


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
