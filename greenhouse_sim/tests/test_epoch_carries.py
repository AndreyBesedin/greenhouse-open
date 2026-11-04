"""An epoch carries what it needs to run (P18.1, decision 0067): a built or an
uploaded scenario runs, is killed and resumes in a worker that has only the
store, under its own weather and site, with the id it was queued under; an epoch
written before epochs carried anything is never given another."""

import json
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.observation import Observation
from pydantic import JsonValue

from greenhouse_sim.api.routes import respond
from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.drafts import DraftStore
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.scenarios.scenario_files import (
    ScenarioFile,
    export_scenario_file,
    import_scenario_file,
)
from greenhouse_sim.services import drafts, leases, scenario_files, scheduler
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.playback import FIRST_EPOCH, Epochs, Playback
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    Kind,
    Status,
    StoreCorrupt,
    StoredRun,
)
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Paced, Stepped, execute, queued
from greenhouse_sim.weather.recorded import checked_recording
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.site import DEFAULT_SITE, Site

# A worker starts from nothing; a test's own scenarios stay in its process.
sys.path.insert(0, str(Path(__file__).parent))

import short_runs
import workers_support

SHORT: Final = workers_support.SHORT
UPLOADED: Final = "uploaded_box"
DRAFT: Final = "built_house"
WAIT_S: Final = 240.0
# Slow enough that the first day is committed well before the second.
SECONDS_PER_DAY: Final = 3
DAYS: Final = 2
SITE: Final = Site(
    latitude_deg=-33.9,
    longitude_deg=18.4,
    elevation_m=120.0,
    time_zone="Africa/Johannesburg",
)
# Three days at the site's own hours: more than a run of `DAYS` reads.
RECORDING: Final = "timestamp,outside_air_temperature_c,outside_relative_humidity_pct\n" + "".join(
    f"2026-04-{day:02d}T{hour:02d}:00+02:00,{3 + hour % 5},{70 + hour}\n"
    for day in range(1, 4)
    for hour in range(24)
)


@pytest.fixture(autouse=True)
def leases_written_often(monkeypatch: pytest.MonkeyPatch) -> None:
    """So that `workers_support.lease_let_go` does not wait for a lease's thread to
    wake, from this test or the one before it. A thread that read the manifest just
    before the epoch ended writes the lease once more: a test that asks anything of
    an epoch it worked here waits for that thread first."""
    monkeypatch.setattr(leases, "REFRESH_EVERY_S", workers_support.LEASE_BEAT_S)


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


def _uploaded_config() -> ScenarioConfig:
    return short_runs.one_plant_box(UPLOADED, DAYS).model_copy(
        update={
            "site": SITE,
            "weather": checked_recording("mine.csv", RECORDING.encode()),
        }
    )


def _house() -> Installation:
    return basic_installation(
        BasicSetup(
            installation_id=DRAFT,
            name="Built house",
            length_m=12.0,
            width_m=6.0,
            eave_height_m=4.0,
            ridge_height_m=4.5,
            rows=2,
            plants_per_row=6,
            plant_pitch_m=0.75,
            row_spacing_m=1.6,
            support_height_m=0.5,
            crop_model=CropModel.SIMPLE,
            variety="cherry_tomato",
        )
    )


def _built(simulator: Simulator) -> str:
    """A draft saved and registered as a scenario, under a site and a weather
    of its own."""
    assert simulator.drafts is not None
    simulator.drafts.save(_house(), on=None)
    asked: dict[str, JsonValue] = {
        "start_date": "2026-04-01",
        "duration_days": DAYS,
        "site": SITE.model_dump(),
        "weather": "cold_spring_day",
    }
    return drafts.run(simulator, DRAFT, None, asked).id


def _upload(simulator: Simulator) -> str:
    text = export_scenario_file(_uploaded_config())
    answer = respond(simulator, "POST", "/api/scenarios/upload", text.encode())
    assert answer.status == HTTPStatus.OK
    return UPLOADED


def _as_older_code_left(objects: FolderStore, epoch: EpochStore) -> None:
    """The epoch's manifest as it was written before epochs carried anything: no
    such keys in it at all."""
    written = json.loads(epoch.manifest().model_dump_json())
    del written["scenario_file"], written["seconds_per_day"]
    objects.put(f"{epoch.run_id}/{epoch.epoch}/manifest.json", json.dumps(written).encode())


def _no_scenario_files(objects: FolderStore) -> None:
    for name in objects.names(scenario_files.KEPT_FOLDER):
        objects.delete(name)


@pytest.mark.parametrize("make", [_built, _upload], ids=["built", "uploaded"])
def test_a_scenario_runs_is_killed_and_resumes_in_a_worker_with_only_the_store(
    tmp_path: Path, make: Callable[[Simulator], str]
) -> None:
    """The acceptance of P18.1: the id it was queued under, and the digests of an
    uninterrupted run, through a server that was closed in between and has
    nothing but the store."""
    objects = FolderStore(tmp_path / "runs")
    drafted = DraftStore(tmp_path / "drafts.sqlite3")
    with Simulator(drafts=drafted, runs=objects) as first:
        scenario_id = make(first)
        config = first.catalogue.entry(scenario_id)
        assert config is not None
        # What a worker would get wrong if it took a default for any of them.
        assert config.config.site == SITE
        assert config.config.weather != ConstantWeather()
        whole = queued(first, FolderStore(tmp_path / "whole"), scenario_id)
        assert execute(first, whole, Free()) == Status.FINISHED
        asked = respond(
            first, "POST", f"/api/scenarios/{scenario_id}/runs?seconds_per_day={SECONDS_PER_DAY}"
        )
        assert asked.status == HTTPStatus.OK and isinstance(asked.body, dict)
        shown = StoredRun.model_validate(asked.body)
        assert shown.run_id == whole.run_id and shown.epoch == whole.epoch
        epoch = EpochStore(objects, shown.run_id, shown.epoch)
        assert epoch.manifest().seconds_per_day == SECONDS_PER_DAY
        assert epoch.manifest().scenario_file is not None
        _until(lambda: epoch.frontier_s() >= DAY_S, "a day to be committed")
        assert first.scheduler is not None
        (worker,) = first.scheduler.workers()
        assert worker.pid != os.getpid()
        os.kill(worker.pid, signal.SIGKILL)
        _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "the epoch to be told")
        _until(lambda: not epoch.worked(), "the lease to be let go")
        assert epoch.frontier_s() == DAY_S

    # A new server, which knows the scenario only from the store.
    with Simulator(runs=objects) as second:
        assert second.catalogue.entry(scenario_id) is not None
        path = f"/api/runs/{shown.run_id}/epochs/{shown.epoch}/resume"
        assert respond(second, "POST", path).status == HTTPStatus.OK
        _until(lambda: epoch.manifest().status == Status.FINISHED, "the epoch to end")

    assert epoch.run_id == whole.run_id
    assert [c.digest for c in epoch.commits()] == [c.digest for c in whole.commits()]
    epoch.verify()


def test_a_fork_of_an_uploaded_scenario_runs_in_a_worker_under_its_weather_and_site(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    with Simulator(runs=objects) as first:
        scenario_id = _upload(first)
        parent = queued(first, objects, scenario_id)
        assert execute(first, parent, Free()) == Status.FINISHED

    with Simulator(runs=objects) as second:
        answer = respond(
            second, "POST", f"/api/runs/{parent.run_id}/epochs/{parent.epoch}/forks?t={DAY_S}"
        )
        assert answer.status == HTTPStatus.OK and isinstance(answer.body, dict)
        kept = EpochStore(objects, parent.run_id, int(str(answer.body["epoch"])))
        assert kept.manifest().scenario_file == parent.manifest().scenario_file
        _until(lambda: kept.manifest().status == Status.FINISHED, "the fork to finish")

    kept.verify()
    assert kept.frontier_s() == DAYS * DAY_S
    # No change was asked: what it worked out from its parent's state, under the
    # same weather and site, is what its parent worked out from there.
    first_day = parent.commits()[0].counts[Kind.OBSERVATIONS]
    assert [_reading(o) for o in kept.observations().records] == [
        _reading(o) for o in parent.observations(after=first_day).records
    ]


def _reading(observation: Observation) -> tuple[object, ...]:
    return (observation.timestamp, observation.observation_type, observation.value)


def test_an_old_epoch_of_a_packaged_scenario_resumes_as_it_was(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path / "runs")
    packaged = "sensor_lab"
    with Simulator(runs=objects) as made:
        kept = queued(made, objects, packaged, seed=5)
        assert execute(made, kept, Stepped([DAY_S])) == Status.INTERRUPTED
        whole = queued(made, FolderStore(tmp_path / "whole"), packaged, seed=5)
        assert execute(made, whole, Stepped([DAY_S, 2 * DAY_S])) == Status.INTERRUPTED
        assert kept.manifest().scenario_file is None
        _as_older_code_left(objects, kept)
        run_id = kept.run_id
        made.scheduler = Scheduler(made, objects.root, limit=1)
        workers_support.lease_let_go(kept)

        assert made.scheduler.resume(run_id, kept.epoch).run_id == run_id
        _until(lambda: kept.frontier_s() >= 2 * DAY_S, "another day of it")
        made.scheduler.cancel(run_id, kept.epoch)

    assert [c.digest for c in kept.commits()[:2]] == [c.digest for c in whole.commits()]
    assert kept.manifest().scenario_file is None


def test_an_old_epoch_of_a_scenario_this_simulator_knows_is_given_its_file_and_resumes(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    with workers_support.short_simulator() as made:
        made.runs = objects
        kept = queued(made, objects, SHORT)
        assert execute(made, kept, Stepped([DAY_S])) == Status.INTERRUPTED
        whole = queued(made, FolderStore(tmp_path / "whole"), SHORT)
        assert execute(made, whole, Free()) == Status.FINISHED
        _as_older_code_left(objects, kept)
        _no_scenario_files(objects)
        made.scheduler = Scheduler(made, objects.root, limit=1)
        workers_support.lease_let_go(kept)

        assert made.scheduler.resume(kept.run_id, kept.epoch).run_id == whole.run_id
        _until(lambda: kept.manifest().status == Status.FINISHED, "the epoch to end")

    assert kept.manifest().scenario_file == whole.manifest().scenario_file
    assert [c.digest for c in kept.commits()] == [c.digest for c in whole.commits()]


def _left_by_older_code(objects: FolderStore) -> EpochStore:
    """An old epoch of a registered scenario, interrupted a day in."""
    with workers_support.short_simulator() as made:
        kept = queued(made, objects, SHORT)
        assert execute(made, kept, Stepped([DAY_S])) == Status.INTERRUPTED
        workers_support.lease_let_go(kept)
    _as_older_code_left(objects, kept)
    _no_scenario_files(objects)
    return kept


def test_an_old_epoch_of_a_scenario_no_one_knows_is_refused_in_words_and_left_alone(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    kept = _left_by_older_code(objects)
    before = objects.get(f"{kept.run_id}/{kept.epoch}/manifest.json")

    with Simulator(runs=objects) as made:
        made.scheduler = Scheduler(made, objects.root, limit=1)
        with pytest.raises(Conflict, match="upload the scenario's file"):
            made.scheduler.resume(kept.run_id, kept.epoch)

    assert objects.get(f"{kept.run_id}/{kept.epoch}/manifest.json") == before


def test_an_old_epoch_of_a_scenario_now_another_never_takes_another_id(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path / "runs")
    kept = _left_by_older_code(objects)
    changed = PACKAGED.configs["climate_box"].model_copy(
        update={"greenhouse_id": SHORT, "duration_days": workers_support.SHORT_DAYS, "name": "No"}
    )

    with Simulator(runs=objects) as made:
        made.catalogue.register(changed)
        made.scheduler = Scheduler(made, objects.root, limit=1)
        with pytest.raises(Conflict, match="knows as another run"):
            made.scheduler.resume(kept.run_id, kept.epoch)

    assert kept.manifest().status == Status.INTERRUPTED
    assert kept.manifest().scenario_file is None
    assert objects.names(scenario_files.KEPT_FOLDER) == []


def test_an_epoch_whose_scenario_file_is_gone_is_refused_when_it_is_asked_to_go_on(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    with workers_support.short_simulator() as made:
        made.runs = objects
        kept = queued(made, objects, SHORT)
        assert execute(made, kept, Stepped([DAY_S])) == Status.INTERRUPTED
        workers_support.lease_let_go(kept)
        _no_scenario_files(objects)
        made.scheduler = Scheduler(made, objects.root, limit=1)

        with pytest.raises(Conflict, match="gone from the store"):
            made.scheduler.resume(kept.run_id, kept.epoch)

    assert kept.manifest().status == Status.INTERRUPTED


def test_a_resume_says_its_own_pace_and_leaves_none_of_the_one_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects = FolderStore(tmp_path / "runs")
    monkeypatch.setattr(scheduler, "work", workers_support.ends_at_once)
    with workers_support.short_simulator() as made:
        made.runs = objects
        made.scheduler = Scheduler(made, objects.root, limit=1)
        shown = made.scheduler.start(SHORT, driver=Paced(SECONDS_PER_DAY))
        epoch = EpochStore(objects, shown.run_id, shown.epoch)
        assert epoch.manifest().seconds_per_day == SECONDS_PER_DAY
        _until(lambda: epoch.manifest().status == Status.FAILED, "the worker to end")
        epoch.set_status(Status.INTERRUPTED)

        made.scheduler.resume(shown.run_id, shown.epoch)

        assert epoch.manifest().seconds_per_day is None


def test_a_scenario_that_cannot_be_written_as_a_file_starts_no_epoch(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path / "runs")
    reference = PACKAGED.configs["reference_greenhouse"]
    fewer = reference.model_copy(update={"greenhouse_id": "fewer", "rows": reference.rows - 1})

    with Simulator() as made:
        made.catalogue.register(fewer)
        with pytest.raises(InvalidRequest, match="cannot be written as a file"):
            queued(made, objects, "fewer")
        # It still plays here, its epoch saying it keeps no file.
        run = Playback(made, "fewer", epochs=Epochs(objects=objects))
        assert EpochStore(objects, run.run_id, FIRST_EPOCH).manifest().scenario_file is None

    assert objects.names(scenario_files.KEPT_FOLDER) == []


def test_a_scenario_that_would_read_back_as_another_starts_no_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects = FolderStore(tmp_path / "runs")

    def another(text: str) -> ScenarioFile:
        read = import_scenario_file(text)
        renamed = read.config.model_copy(update={"name": "Another"})
        return ScenarioFile(renamed, read.recording, read.digest)

    monkeypatch.setattr(scenario_files, "import_scenario_file", another)
    with (
        workers_support.short_simulator() as made,
        pytest.raises(InvalidRequest, match="does not read back"),
    ):
        queued(made, objects, SHORT)
    assert objects.children() == []


def test_a_playback_kept_in_the_store_carries_its_scenario_as_a_queued_epoch_does(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    with workers_support.short_simulator() as made:
        run = Playback(made, SHORT, epochs=Epochs(objects=objects))
        kept = EpochStore(objects, run.run_id, FIRST_EPOCH)
        named = kept.manifest().scenario_file
        assert named is not None and objects.get(scenario_files.kept_name(named)) is not None
    # A packaged one's is every simulator's, and is not written.
    with Simulator() as made:
        run = Playback(made, "climate_box", epochs=Epochs(objects=objects))
        assert EpochStore(objects, run.run_id, FIRST_EPOCH).manifest().scenario_file is None


def test_a_file_an_epoch_names_is_refused_if_it_is_not_that_file(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path / "runs")
    with workers_support.short_simulator() as made:
        kept = queued(made, objects, SHORT)
    named = kept.manifest().scenario_file
    assert named is not None
    other = export_scenario_file(_uploaded_config())
    objects.put(scenario_files.kept_name(named), other.encode())

    with Simulator() as worker, pytest.raises(StoreCorrupt, match="not what it says"):
        scenario_files.take_up(worker, objects, named)
    objects.delete(scenario_files.kept_name(named))
    with Simulator() as worker, pytest.raises(StoreCorrupt, match="is gone"):
        scenario_files.take_up(worker, objects, named)


def _named_as_the_uploaded(tmp_path: Path) -> Simulator:
    """A simulator with a scenario uploaded, and a draft named as it is, as the
    builder saves a draft opened from a file."""
    made = Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3"))
    constant = ConstantWeather(air_temperature_c=3.0)
    source = _uploaded_config().model_copy(
        update={"weather": constant, "cloud_cover_pct": 40.0, "wind_from_deg": 90.0}
    )
    text = export_scenario_file(source)
    assert respond(made, "POST", "/api/scenarios/upload", text.encode()).status == HTTPStatus.OK
    assert made.drafts is not None
    made.drafts.save(
        _house().model_copy(update={"installation_id": UPLOADED}),
        on=None,
    )
    return made


A_RUN: Final[dict[str, JsonValue]] = {"start_date": "2026-04-01", "duration_days": 1}


def test_a_draft_of_an_uploaded_scenario_runs_under_its_weather_and_site(tmp_path: Path) -> None:
    with _named_as_the_uploaded(tmp_path) as made:
        ran = drafts.run(made, UPLOADED, None, A_RUN)
        entry = made.catalogue.entry(ran.id)
        source = made.catalogue.entry(UPLOADED)
        assert entry is not None and source is not None

        assert entry.config.site == SITE
        assert entry.config.weather == source.config.weather
        assert entry.config.cloud_cover_pct == 40.0
        assert entry.config.wind_from_deg == 90.0


def test_a_draft_of_a_recorded_scenario_keeps_the_recording_it_was_uploaded_with(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    made = Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3"), runs=objects)
    with made:
        _upload(made)
        assert made.drafts is not None
        made.drafts.save(_house().model_copy(update={"installation_id": UPLOADED}), on=None)

        ran = drafts.run(made, UPLOADED, None, A_RUN | {"duration_days": DAYS})
        kept = queued(made, objects, ran.id)

    named = kept.manifest().scenario_file
    assert named is not None
    with Simulator() as worker:
        scenario_files.take_up(worker, objects, named)
        entry = worker.catalogue.entry(ran.id)
    assert entry is not None and entry.config.weather == _uploaded_config().weather


@pytest.mark.parametrize(
    ("weather", "clouds", "wind", "seed"),
    [
        ("default@80", 80.0, 90.0, 0),
        ("default~270", 40.0, 270.0, 0),
        ("default#7", 40.0, 90.0, 7),
        ("default@80~270#7", 80.0, 270.0, 7),
    ],
)
def test_a_draft_of_an_uploaded_scenario_changes_only_what_its_weather_overrides(
    tmp_path: Path, weather: str, clouds: float, wind: float, seed: int
) -> None:
    with _named_as_the_uploaded(tmp_path) as made:
        ran = drafts.run(made, UPLOADED, None, A_RUN | {"weather": weather})
        entry = made.catalogue.entry(ran.id)
        source = made.catalogue.entry(UPLOADED)
        assert entry is not None and source is not None

        assert entry.config.weather == source.config.weather
        assert entry.config.site == SITE
        assert (entry.config.cloud_cover_pct, entry.config.wind_from_deg) == (clouds, wind)
        assert entry.config.random_seed == seed


def test_a_worker_goes_at_the_pace_its_epoch_names(tmp_path: Path) -> None:
    """A day is written once the clock has passed it, so that the commits of a
    house this quick to work out lie a pace apart."""
    objects = FolderStore(tmp_path / "runs")
    with Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3"), runs=objects) as made:
        scenario_id = _built(made)
        shown = respond(
            made, "POST", f"/api/scenarios/{scenario_id}/runs?seconds_per_day={SECONDS_PER_DAY}"
        )
        assert isinstance(shown.body, dict)
        epoch = EpochStore(objects, str(shown.body["run_id"]), int(str(shown.body["epoch"])))
        _until(lambda: epoch.manifest().status == Status.FINISHED, "the epoch to end")

    first, second = sorted(objects.root.glob(f"{epoch.run_id}/{epoch.epoch}/commits/*.json"))
    assert second.stat().st_mtime - first.stat().st_mtime > SECONDS_PER_DAY / 2


def test_a_draft_of_a_scenario_runs_under_the_site_and_weather_it_asks_for(tmp_path: Path) -> None:
    with _named_as_the_uploaded(tmp_path) as made:
        ran = drafts.run(
            made,
            UPLOADED,
            None,
            A_RUN
            | {
                "scenario_id": "asked",
                "site": DEFAULT_SITE.model_dump(),
                "weather": "cold_spring_day",
            },
        )
        entry = made.catalogue.entry(ran.id)
        assert entry is not None

        assert entry.config.site == DEFAULT_SITE
        assert entry.config.weather != ConstantWeather(air_temperature_c=3.0)
        assert entry.config.cloud_cover_pct is None and entry.config.wind_from_deg is None


def test_a_draft_named_as_nothing_or_as_a_packaged_scenario_has_the_defaults(
    tmp_path: Path,
) -> None:
    with Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3")) as made:
        assert made.drafts is not None
        made.drafts.save(_house(), on=None)
        made.drafts.save(_house().model_copy(update={"installation_id": "climate_box"}), on=None)

        for draft_id in (DRAFT, "climate_box"):
            entry = made.catalogue.entry(drafts.run(made, draft_id, None, A_RUN).id)
            assert entry is not None
            assert entry.config.site == DEFAULT_SITE
            assert entry.config.weather == ConstantWeather()


def test_an_old_manifest_is_read_and_says_it_carries_nothing() -> None:
    written = (
        b'{"format":"run-store-1","run_id":"a","epoch":0,"scenario_id":"b","layout":"default"}'
    )

    manifest = EpochManifest.model_validate_json(written)

    assert manifest.scenario_file is None and manifest.seconds_per_day is None
