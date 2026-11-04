"""Reports for the epochs kept before they were written (P18.2, decision 0067),
so that a list of them reads a report and need not walk each.

A list never writes to the store, so this is done once, by a command
(`greenhouse_sim.usage_reports`). It adds one object to an epoch, its report
(`usage.json`), in no digest, and changes no other: no manifest, segment,
checkpoint or commit, and so no run id, digest or position.

The report says what the epoch's objects say, as its next worker's would. Its
`cpu_s` and `peak_memory_bytes` are none, which is not zero: no worker measured
them, and nothing that reads the epoch now can. A worker that carries it on
later counts its own from there.

It leaves alone:

- an epoch with a report, which may hold what its workers measured, and one whose
  report cannot be read, which is said to have failed and is not written over;
- an epoch queued, running or with a lease: its worker writes its report, or
  will, and one running that no one works gets one as a server starts and finds
  it interrupted;
- an epoch with an object missing that its commits name, which is said to have
  failed: a list that found its report would count its folders and stop seeing
  that it is damaged, whereas without one it goes on walking this one epoch.

Objects are not read for their digests (`EpochStore.verify`), which costs a read
of each: a report says nothing of what they hold.
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto

from greenhouse_sim.services.run_store import (
    USAGE,
    EpochManifest,
    EpochStore,
    EpochUsage,
    ObjectStore,
    Status,
    StoreCorrupt,
    started_epochs,
)


class _Done(Enum):
    WRITTEN = auto()
    HAD_REPORT = auto()
    BEING_WORKED = auto()


@dataclass(frozen=True)
class NotReported:
    """An epoch, or a run's folder, this could not report, and why."""

    where: str
    reason: str


@dataclass(frozen=True)
class Reported:
    """What was done to a store: how many epochs were given a report, how many
    were left as having one or as being worked, and those that failed."""

    written: int
    had_report: int
    being_worked: int
    failed: tuple[NotReported, ...]


def report_missing(objects: ObjectStore) -> Reported:
    """Gives each epoch in `objects` that lacks one its report. An epoch that
    fails, for whatever reason, is said to have, and the rest go on."""
    done: Counter[_Done] = Counter()
    failed: list[NotReported] = []
    for run_id in objects.children():
        try:
            numbers = started_epochs(objects, run_id)
        except OSError as error:
            failed.append(NotReported(run_id, _said(error)))
            continue
        for number in numbers:
            try:
                found = _report(EpochStore(objects, run_id, number))
            except Exception as error:
                failed.append(NotReported(f"{run_id}/{number}", _said(error)))
            else:
                if found is not None:
                    done[found] += 1
    return Reported(
        written=done[_Done.WRITTEN],
        had_report=done[_Done.HAD_REPORT],
        being_worked=done[_Done.BEING_WORKED],
        failed=tuple(failed),
    )


def _report(epoch: EpochStore) -> _Done | None:
    """What was done to one epoch; none if it is not one: deleted, or a fork cut
    short, which keeps a folder and no manifest."""
    home = f"{epoch.run_id}/{epoch.epoch}"
    if epoch.objects.get(f"{home}/manifest.json") is None:
        return None
    if _being_worked(epoch, epoch.manifest()):
        return _Done.BEING_WORKED
    report = epoch.objects.get(f"{home}/{USAGE}")
    if report is not None:
        EpochUsage.model_validate_json(report)
        return _Done.HAD_REPORT
    commits = epoch.commits()
    if epoch.damaged(commits):
        raise StoreCorrupt("files of it are missing, so it is left to be walked")
    # Looked at again just before the write: a worker may have taken it up since.
    if _being_worked(epoch, epoch.manifest()):
        return _Done.BEING_WORKED
    epoch.write_usage(commits)
    return _Done.WRITTEN


def _being_worked(epoch: EpochStore, manifest: EpochManifest) -> bool:
    return manifest.status in (Status.QUEUED, Status.RUNNING) or epoch.worked()


def _said(error: Exception) -> str:
    """An error, for whoever runs the command: its kind and its first line, for
    what a model's validation says goes on for a page."""
    text = str(error).partition("\n")[0]
    return f"{type(error).__name__}: {text}" if text else type(error).__name__
