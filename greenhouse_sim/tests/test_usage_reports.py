"""The command that gives old epochs their reports (P18.2, decision 0067): it adds
reports and changes nothing else, leaves what it should, says what it did, and
what it cannot know it says is absent."""

import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from greenhouse_sim import usage_reports
from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import leases
from greenhouse_sim.services.resources import ProcessUse
from greenhouse_sim.services.run_store import (
    USAGE,
    EpochManifest,
    EpochStore,
    FolderStore,
    ForkOf,
    Status,
    delete_epoch,
    stored_runs,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.usage_reports import NotReported, Reported, report_missing

A_DAYS_EVENTS = "segments/0000000000000000-0000086400000000/events.parquet"
NOTHING: Reported = Reported(written=0, had_report=0, being_worked=0, failed=())


def _old(root: Path, run_id: str = "run_a", *, status: Status = Status.FINISHED) -> EpochStore:
    """Two days of an epoch as one kept before reports is: no report, and a
    manifest that does not know the field a failure's reason is in."""
    objects = FolderStore(root)
    store = EpochStore.create(
        objects,
        EpochManifest(
            run_id=run_id,
            epoch=0,
            scenario_id="s",
            layout="default",
            status=status,
            duration_s=2 * DAY_S,
        ),
    )
    store.commit(0.0, DAY_S, checkpoint=b"first")
    store.commit(DAY_S, 2 * DAY_S, checkpoint=b"second")
    objects.delete(f"{run_id}/0/{USAGE}")
    manifest = json.loads(objects.get(f"{run_id}/0/manifest.json") or b"")
    del manifest["reason"]
    objects.put(f"{run_id}/0/manifest.json", json.dumps(manifest).encode())
    return store


def _old_fork(root: Path, run_id: str = "run_f") -> EpochStore:
    """A fork from before reports, its state inherited and its first day its own."""
    objects = FolderStore(root)
    store = EpochStore(objects, run_id, 0)
    state = b"the state it inherits"
    store.write_fork(
        EpochManifest(
            run_id=run_id,
            epoch=0,
            scenario_id="s",
            layout="default",
            status=Status.INTERRUPTED,
            duration_s=3 * DAY_S,
            fork=ForkOf(
                run_id="run_a",
                epoch=0,
                at_s=DAY_S,
                start_s=DAY_S,
                digest="a",
                checkpoint_sha256=hashlib.sha256(state).hexdigest(),
            ),
        ),
        state=state,
        log=(),
        outcomes=(),
    )
    store.commit(DAY_S, 2 * DAY_S, checkpoint=b"its own")
    objects.delete(f"{run_id}/0/{USAGE}")
    return store


def _files(root: Path) -> dict[str, tuple[str, int]]:
    """Every file under `root`, what it holds and when it was last written."""
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def _a_claim(store: EpochStore) -> None:
    store.objects.create(
        f"{store.run_id}/{store.epoch}/{leases.CLAIMS}/00000000.json",
        json.dumps({"refreshed_at": time.time()}).encode(),
    )


def _meter(cpu_s: float, peak: int) -> Callable[[], ProcessUse]:
    return lambda: ProcessUse(cpu_s, peak)


def test_each_old_epoch_gets_a_report_and_a_list_says_of_it_what_it_said(tmp_path: Path) -> None:
    _old(tmp_path, "run_a")
    _old(tmp_path, "run_b", status=Status.INTERRUPTED)
    _old_fork(tmp_path)
    objects = FolderStore(tmp_path)
    before = stored_runs(objects)

    done = report_missing(objects)

    assert done == Reported(written=3, had_report=0, being_worked=0, failed=())
    assert stored_runs(objects) == before
    assert [EpochStore(objects, r.run_id, 0).usage() is not None for r in before] == [True] * 3


def test_a_list_after_it_walks_nothing(tmp_path: Path) -> None:
    class Counted(FolderStore):
        commits_read = 0

        def get(self, name: str) -> bytes | None:
            Counted.commits_read += "/commits/" in name
            return super().get(name)

    _old(tmp_path)
    objects = Counted(tmp_path)
    stored_runs(objects)
    assert Counted.commits_read == 2
    report_missing(objects)
    Counted.commits_read = 0

    stored_runs(objects)

    assert Counted.commits_read == 0


def test_it_changes_no_other_file_of_the_store(tmp_path: Path) -> None:
    run = _old(tmp_path)
    _old_fork(tmp_path)
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "abc.json").write_text("{}")
    before = _files(tmp_path)
    digests = [commit.digest for commit in run.commits()]

    report_missing(FolderStore(tmp_path))

    after = _files(tmp_path)
    added = set(after) - set(before)
    assert added == {f"run_a/0/{USAGE}", f"run_f/0/{USAGE}"}, "nothing partial is left, either"
    assert {name: after[name] for name in before} == before
    assert [commit.digest for commit in run.commits()] == digests
    run.verify()


def test_running_it_twice_changes_nothing(tmp_path: Path) -> None:
    _old(tmp_path)
    objects = FolderStore(tmp_path)
    report_missing(objects)
    before = _files(tmp_path)

    again = report_missing(objects)

    assert again == Reported(written=0, had_report=1, being_worked=0, failed=())
    assert _files(tmp_path) == before


def test_a_report_its_workers_wrote_is_left_as_it_is(tmp_path: Path) -> None:
    store = _old(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.report_usage()
    before = _files(tmp_path)

    done = report_missing(store.objects)

    assert done == Reported(written=0, had_report=1, being_worked=0, failed=())
    assert _files(tmp_path) == before


@pytest.mark.parametrize(
    ("status", "leased"),
    [
        (Status.RUNNING, True),
        (Status.INTERRUPTED, True),
        (Status.FINISHED, True),
        (Status.QUEUED, False),
        (Status.RUNNING, False),
    ],
)
def test_an_epoch_being_worked_is_left_alone(tmp_path: Path, status: Status, leased: bool) -> None:
    store = _old(tmp_path, status=status)
    if leased:
        _a_claim(store)
    before = _files(tmp_path)

    done = report_missing(store.objects)

    assert done == Reported(written=0, had_report=0, being_worked=1, failed=())
    assert _files(tmp_path) == before


def test_an_epoch_a_worker_takes_up_as_it_is_read_is_left_to_its_worker(tmp_path: Path) -> None:
    class TakenUp(FolderStore):
        def names(self, prefix: str = "") -> list[str]:
            _a_claim(EpochStore(self, "run_a", 0))
            return super().names(prefix)

    _old(tmp_path)

    done = report_missing(TakenUp(tmp_path))

    assert done == Reported(written=0, had_report=0, being_worked=1, failed=())
    assert not (tmp_path / "run_a" / "0" / USAGE).exists()


@pytest.mark.parametrize("name", [f"{leases.CLAIMS}/00000000.json", leases.LEASE])
def test_a_claim_long_expired_is_no_one_working_it(tmp_path: Path, name: str) -> None:
    store = _old(tmp_path, status=Status.INTERRUPTED)
    store.objects.put(f"run_a/0/{name}", json.dumps({"refreshed_at": 1.0}).encode())

    assert report_missing(store.objects).written == 1


def test_what_no_worker_measured_is_absent_and_not_zero(tmp_path: Path) -> None:
    store = _old(tmp_path)
    report_missing(store.objects)

    written = json.loads((tmp_path / "run_a" / "0" / USAGE).read_text())
    assert written["cpu_s"] is None and written["peak_memory_bytes"] is None
    assert written["commits"] == 2 and written["days_computed"] == 2.0

    with Simulator(runs=store.objects) as simulator:
        listed = respond(simulator, "GET", "/api/runs")
        one = respond(simulator, "GET", "/api/runs/run_a/epochs/0")
    assert isinstance(listed.body, list)
    (row,) = listed.body
    assert isinstance(row, dict) and row == one.body
    assert row["cpu_s"] is None and row["peak_memory_bytes"] is None
    assert row["days_computed"] == 2.0


def test_a_worker_that_carries_it_on_counts_only_its_own(tmp_path: Path) -> None:
    store = _old(tmp_path, status=Status.INTERRUPTED)
    report_missing(store.objects)

    worker = EpochStore(store.objects, "run_a", 0)
    worker.counted_by(_meter(3.0, 100))
    worker.report_usage()

    usage = worker.usage()
    assert usage is not None and (usage.cpu_s, usage.peak_memory_bytes) == (3.0, 100)


def test_a_damaged_epoch_is_not_given_a_report_that_would_hide_it(tmp_path: Path) -> None:
    """With a report, a list counts folders and stops seeing a file lost from
    inside a day's: without one it goes on walking this epoch and says so."""
    store = _old(tmp_path)
    store.objects.delete(f"run_a/0/{A_DAYS_EVENTS}")
    assert stored_runs(store.objects)[0].damaged

    done = report_missing(store.objects)

    assert done.written == 0 and [failed.where for failed in done.failed] == ["run_a/0"]
    assert "files of it are missing" in done.failed[0].reason
    assert not (tmp_path / "run_a" / "0" / USAGE).exists()
    assert stored_runs(store.objects)[0].damaged


def test_a_finished_epoch_short_of_its_end_is_not_given_a_report_that_would_hide_it(
    tmp_path: Path,
) -> None:
    """A report counting the commits left would agree with its folders, and a list
    would stop seeing that the last of them are gone."""
    store = _old(tmp_path)
    store.objects.delete("run_a/0/commits/00000001.json")

    done = report_missing(store.objects)

    assert done.written == 0 and [failed.where for failed in done.failed] == ["run_a/0"]
    assert not (tmp_path / "run_a" / "0" / USAGE).exists()
    assert stored_runs(store.objects)[0].damaged


def _garbled_manifest(store: EpochStore) -> None:
    store.objects.put(f"{store.run_id}/0/manifest.json", b"not a manifest")


def _garbled_commit(store: EpochStore) -> None:
    store.objects.put(f"{store.run_id}/0/commits/00000000.json", b"not a commit")


def _garbled_report(store: EpochStore) -> None:
    store.objects.put(f"{store.run_id}/0/{USAGE}", b"not a report")


@pytest.mark.parametrize(
    ("garble", "said"),
    [
        (_garbled_manifest, "EpochManifest"),
        (_garbled_commit, "Commit"),
        (_garbled_report, "EpochUsage"),
    ],
)
def test_an_epoch_it_cannot_read_is_said_and_the_rest_go_on(
    tmp_path: Path, garble: Callable[[EpochStore], None], said: str
) -> None:
    _old(tmp_path, "run_a")
    broken = _old(tmp_path, "run_b")
    garble(broken)
    _old(tmp_path, "run_c")
    before = _files(tmp_path / "run_b")

    done = report_missing(FolderStore(tmp_path))

    assert done.written == 2
    (failed,) = done.failed
    assert failed.where == "run_b/0" and failed.reason.startswith("ValidationError: ")
    assert said in failed.reason and "\n" not in failed.reason
    assert _files(tmp_path / "run_b") == before, "a report it cannot read is not written over"


def test_a_disk_that_refuses_a_report_fails_that_epoch_and_no_other(tmp_path: Path) -> None:
    class Full(FolderStore):
        def put(self, name: str, data: bytes) -> None:
            if name.startswith("run_b/"):
                raise OSError(28, "No space left on device")
            super().put(name, data)

    _old(tmp_path, "run_a")
    _old(tmp_path, "run_b")
    _old(tmp_path, "run_c")

    done = report_missing(Full(tmp_path))

    assert done == Reported(
        written=2,
        had_report=0,
        being_worked=0,
        failed=(NotReported("run_b/0", "OSError: [Errno 28] No space left on device"),),
    )


def test_a_run_whose_folder_cannot_be_listed_is_said_and_the_rest_go_on(tmp_path: Path) -> None:
    class Refusing(FolderStore):
        def children(self, prefix: str = "") -> list[str]:
            if prefix == "run_b/":
                raise PermissionError(13, "Permission denied")
            return super().children(prefix)

    _old(tmp_path, "run_a")
    _old(tmp_path, "run_b")
    _old(tmp_path, "run_c")

    done = report_missing(Refusing(tmp_path))

    assert done.written == 2 and [failed.where for failed in done.failed] == ["run_b"]


def test_an_epoch_deleted_or_cut_short_is_no_epoch(tmp_path: Path) -> None:
    deleted = _old(tmp_path, "run_a")
    delete_epoch(deleted.objects, "run_a", 0)
    (tmp_path / "run_b" / "0" / "checkpoints").mkdir(parents=True)
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "abc.json").write_text("{}")
    before = _files(tmp_path)

    assert report_missing(FolderStore(tmp_path)) == NOTHING
    assert _files(tmp_path) == before


def test_a_report_counts_what_a_crash_left_past_the_last_commit_as_a_list_did(
    tmp_path: Path,
) -> None:
    """A crash leaves a day's objects past the last commit: not missing, and
    counted in its size as a list counted them."""
    store = _old(tmp_path, status=Status.INTERRUPTED)
    store.objects.put("run_a/0/segments/left-by-a-crash/events.parquet", b"left")
    before = stored_runs(store.objects)

    assert report_missing(store.objects).written == 1
    assert stored_runs(store.objects) == before


def test_the_command_says_what_it_did(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _old(tmp_path, "run_a")
    _old(tmp_path, "run_b")
    leased = _old(tmp_path, "run_c")
    _a_claim(leased)
    garbled = _old(tmp_path, "run_d")
    first_commit = "run_d/0/commits/00000000.json"
    whole = garbled.objects.get(first_commit)
    assert whole is not None
    _garbled_commit(garbled)

    assert usage_reports.main([str(tmp_path)]) == 1
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "2 written, 0 skipped with a report, 1 skipped as being worked, 1 failed"
    assert printed[1].startswith("failed run_d/0: ValidationError: ") and len(printed) == 2

    garbled.objects.put(first_commit, whole)
    assert usage_reports.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "1 written, 2 skipped with a report, 1 skipped as being worked, 0 failed\n"
    )


def test_the_command_refuses_a_folder_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        usage_reports.main([str(tmp_path / "no-such-store")])
    assert refused.value.code == 2


def test_the_command_runs_as_a_module(tmp_path: Path) -> None:
    _old(tmp_path)

    ran = subprocess.run(
        [sys.executable, "-m", "greenhouse_sim.usage_reports", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.startswith("1 written, ")
    assert (tmp_path / "run_a" / "0" / USAGE).exists()
