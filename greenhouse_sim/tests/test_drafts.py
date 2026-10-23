"""Drafts kept locally, with their revisions (P12.1, decision 0051): saved,
reopened, reverted and deleted, a change on a stale revision refused, and
kept in a file a later store reads."""

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.drafts import (
    STORE_FORMAT,
    DraftNotFound,
    DraftStore,
    DraftStoreError,
    StaleDraft,
)
from greenhouse_sim.builder.portable import export_installation
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.installation import Installation

START = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


def _house(name: str = "Test house", installation_id: str = "my_greenhouse") -> Installation:
    return basic_installation(
        BasicSetup(
            installation_id=installation_id,
            name=name,
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


class _Clock:
    """A minute later at each save."""

    def __init__(self) -> None:
        self.moment = START

    def __call__(self) -> datetime:
        self.moment += timedelta(minutes=1)
        return self.moment


def _store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts" / "drafts.sqlite3", now=_Clock())


def test_a_draft_is_saved_revision_by_revision_and_reopened_at_any(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.save(_house(), on=None)
    second = store.save(_house(name="Renamed house"), on=first.revision)

    assert (first.revision, second.revision) == (1, 2)
    assert store.open("my_greenhouse") == second
    assert store.open("my_greenhouse", 1) == first
    assert store.open("my_greenhouse", 1).installation == _house()
    assert [(each.revision, each.name) for each in store.revisions("my_greenhouse")] == [
        (1, "Test house"),
        (2, "Renamed house"),
    ]
    assert first.saved_at < second.saved_at


def test_drafts_are_listed_as_their_latest_revisions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_house(installation_id="b_house", name="B"), on=None)
    store.save(_house(installation_id="a_house", name="A"), on=None)
    latest = store.save(_house(installation_id="b_house", name="B, later"), on=1)

    listed = store.drafts()

    assert [(each.draft_id, each.name, each.revision) for each in listed] == [
        ("a_house", "A", 1),
        ("b_house", "B, later", 2),
    ]
    assert listed[1].saved_at == latest.saved_at


def test_a_change_on_a_revision_no_longer_the_latest_is_refused(tmp_path: Path) -> None:
    """As by another window of the editor: nothing it saved is lost."""
    store = _store(tmp_path)
    store.save(_house(), on=None)
    store.save(_house(name="Saved elsewhere"), on=1)

    with pytest.raises(StaleDraft, match="at revision 2, not 1: another was saved since"):
        store.save(_house(name="Saved here"), on=1)
    with pytest.raises(StaleDraft, match="kept already, at revision 2"):
        store.save(_house(name="A new one"), on=None)
    with pytest.raises(StaleDraft, match="at revision 2, not 1"):
        store.revert("my_greenhouse", 1, on=1)
    with pytest.raises(StaleDraft, match="at revision 2, not 1"):
        store.delete("my_greenhouse", on=1)
    with pytest.raises(StaleDraft, match="no draft 'elsewhere' to save revision 1 on"):
        store.save(_house(installation_id="elsewhere"), on=1)

    assert store.open("my_greenhouse").installation.name == "Saved elsewhere"
    assert len(store.revisions("my_greenhouse")) == 2


def test_two_stores_on_one_file_refuse_each_others_stale_changes(tmp_path: Path) -> None:
    path = tmp_path / "drafts.sqlite3"
    one, other = DraftStore(path), DraftStore(path)
    one.save(_house(), on=None)
    other.save(_house(name="From the other"), on=1)

    with pytest.raises(StaleDraft):
        one.save(_house(name="From the one"), on=1)
    assert one.open("my_greenhouse").installation.name == "From the other"


def test_saves_at_once_on_one_revision_keep_one_and_refuse_the_others(tmp_path: Path) -> None:
    """Each save reads the latest revision and writes the next in one
    transaction holding the write lock: of saves on the same revision at
    the same time, one is kept and the others are told it is stale."""
    path = tmp_path / "drafts.sqlite3"
    DraftStore(path).save(_house(), on=None)
    savers = 8
    ready = threading.Barrier(savers)
    outcomes: list[str] = []

    def save(number: int) -> None:
        store = DraftStore(path)
        ready.wait()
        try:
            store.save(_house(name=f"Saver {number}"), on=1)
            outcomes.append("saved")
        except StaleDraft:
            outcomes.append("stale")
        except sqlite3.Error as error:
            outcomes.append(f"failed: {error}")

    threads = [threading.Thread(target=save, args=(number,)) for number in range(savers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["saved"] + ["stale"] * (savers - 1)
    assert len(DraftStore(path).revisions("my_greenhouse")) == 2


def test_reverting_saves_an_earlier_revision_again_as_the_latest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_house(), on=None)
    store.save(_house(name="Changed"), on=1)

    reverted = store.revert("my_greenhouse", 1, on=2)

    assert reverted.revision == 3
    assert reverted.installation == _house()
    assert store.open("my_greenhouse") == reverted
    assert store.open("my_greenhouse", 2).installation.name == "Changed"


def test_a_deleted_draft_is_gone_with_its_revisions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_house(), on=None)
    store.save(_house(name="Changed"), on=1)

    store.delete("my_greenhouse", on=2)

    assert store.drafts() == []
    with pytest.raises(DraftNotFound, match="no draft 'my_greenhouse'"):
        store.open("my_greenhouse")
    # Its identifier is free again, from revision 1.
    assert store.save(_house(), on=None).revision == 1


def test_what_is_not_kept_is_not_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_house(), on=None)

    with pytest.raises(DraftNotFound, match="no draft 'elsewhere'"):
        store.open("elsewhere")
    with pytest.raises(DraftNotFound, match="no revision 5 of draft 'my_greenhouse'"):
        store.open("my_greenhouse", 5)
    with pytest.raises(DraftNotFound, match="no revision 5"):
        store.revert("my_greenhouse", 5, on=1)
    with pytest.raises(DraftNotFound, match="no draft 'elsewhere'"):
        store.revisions("elsewhere")
    with pytest.raises(DraftNotFound, match="no draft 'elsewhere'"):
        store.delete("elsewhere", on=1)
    assert len(store.revisions("my_greenhouse")) == 1


def test_a_draft_that_cannot_be_written_is_not_saved(tmp_path: Path) -> None:
    store = _store(tmp_path)
    house = _house()
    unwritable = house.model_copy(
        update={"envelope": house.envelope.model_copy(update={"length": float("nan")})}
    )

    with pytest.raises(ValueError, match="JSON"):
        store.save(unwritable, on=None)
    assert store.drafts() == []


def test_the_drafts_stay_in_their_file_for_a_later_store(tmp_path: Path) -> None:
    path = tmp_path / "drafts.sqlite3"
    saved = DraftStore(path, now=_Clock()).save(_house(), on=None)

    assert DraftStore(path).open("my_greenhouse") == saved


def test_a_revision_kept_in_an_older_format_is_read_as_its_file_is(tmp_path: Path) -> None:
    """A revision is kept as its installation's file; one saved in format 3
    is read as a file in format 3 is."""
    path = tmp_path / "drafts.sqlite3"
    store = DraftStore(path, now=_Clock())
    store.save(_house(), on=None)
    older = json.dumps(json.loads(export_installation(_house())) | {"schema_version": 3})
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE revisions SET document = ?", (older,))

    assert store.open("my_greenhouse").installation == _house()


def test_a_file_that_is_no_store_of_drafts_is_refused(tmp_path: Path) -> None:
    text = tmp_path / "notes.sqlite3"
    text.write_text("not a database, though named as one\n" * 100)
    with pytest.raises(DraftStoreError, match="not a store of drafts"):
        DraftStore(text)

    other = tmp_path / "other.sqlite3"
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE elsewhere (value TEXT)")
    with pytest.raises(DraftStoreError, match="in format 0"):
        DraftStore(other)

    later = tmp_path / "later.sqlite3"
    DraftStore(later)
    with sqlite3.connect(later) as connection:
        connection.execute(f"PRAGMA user_version = {STORE_FORMAT + 1}")
    with pytest.raises(DraftStoreError, match=f"in format {STORE_FORMAT + 1}; this simulator"):
        DraftStore(later)
