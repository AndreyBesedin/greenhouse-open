"""The services' kept values, in one kind of store (AUDIT.7, AUDIT.29, W9):
a value made once, outside its store's lock, requests for it waiting for
the one that makes it and requests for anything else not; a value whose
making fails not kept; the latest kept up to a bound, beside those pinned;
what is let go handed on outside the lock; and everything forgotten at
once, the stores made last first."""

import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from greenhouse_sim.services import fields
from greenhouse_sim.services.stores import Store, forget_everything

# Long enough for a thread that is not stalled to finish.
WAIT_S = 5.0
POLL_S = 0.01
TESTS = Path(__file__).parent
# A store's own forgetting, called by a test file rather than by conftest's
# fixtures.
OWN_FORGETTING = re.compile(r"\.forget\(\)|\bforget_(?!everything)\w+\(|stop_playbacks\(")


def _making(value: str) -> Callable[[list[tuple[str, str]]], str]:
    """Makes `value`, whatever is kept."""
    return lambda others: value


def test_a_value_is_made_once_and_given_to_everyone_who_asks() -> None:
    store: Store[str, str] = Store("test", 4)
    started, finish = threading.Event(), threading.Event()
    made: list[str] = []

    def make(others: list[tuple[str, str]]) -> str:
        made.append("a")
        started.set()
        finish.wait(WAIT_S)
        return "A"

    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(store.made_once, "a", make)
        assert started.wait(WAIT_S)
        others = [pool.submit(store.made_once, "a", make) for _ in range(3)]
        finish.set()
        assert [first.result(), *(other.result() for other in others)] == ["A"] * 4
    assert made == ["a"]


def test_making_one_value_holds_up_no_other() -> None:
    store: Store[str, str] = Store("test", 4)
    finish = threading.Event()

    def slow(others: list[tuple[str, str]]) -> str:
        finish.wait(WAIT_S)
        return "A"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(store.made_once, "a", slow)
        assert store.made_once("b", _making("B")) == "B"
        assert not first.done()
        finish.set()
        assert first.result() == "A"


def test_a_value_is_made_from_the_related_values_kept_before_it() -> None:
    store: Store[str, str] = Store("test", 4)
    for key in ("a1", "b1"):
        store.made_once(key, _making(key.upper()))
    seen: list[list[tuple[str, str]]] = []

    def make(others: list[tuple[str, str]]) -> str:
        seen.append(others)
        return "A2"

    store.made_once("a2", make, lambda other: other.startswith("a"))

    assert seen == [[("a1", "A1")]]
    assert store.values() == [("a1", "A1"), ("b1", "B1"), ("a2", "A2")]


def test_the_latest_values_are_kept_up_to_the_bound_beside_those_pinned() -> None:
    dropped: list[str] = []
    store: Store[str, str] = Store("test", 2, on_drop=lambda key, _: dropped.append(key))
    store.keep("opening", "O", pinned=True)
    for key in ("a", "b", "c"):
        store.made_once(key, _making(key))
    store.made_once("b", _making("again"))

    assert store.values() == [("opening", "O"), ("c", "c"), ("b", "b")]
    assert dropped == ["a"]
    assert store.get("a") is None and store.get("opening") == "O"
    store.keep("d", "d")
    assert [key for key, _ in store.values()] == ["opening", "b", "d"]
    assert dropped == ["a", "c"]


def test_what_is_let_go_is_handed_on_outside_the_lock() -> None:
    # Handed on under the lock, a hook that asks the store again would wait
    # for itself: the hook looks whether the lock is held, without waiting.
    held: list[bool] = []
    store: Store[str, str] = Store("test", 1, on_drop=lambda *_: held.append(store._lock.locked()))
    store.keep("a", "A")
    store.keep("b", "B")
    store.made_once("c", _making("C"))
    store.drop("c")
    store.keep("d", "D", pinned=True)
    store.forget()

    assert held == [False] * 4


def test_a_drop_told_late_leaves_a_value_kept_since() -> None:
    # Told to let a value go once it was replaced, a drop leaves the new one.
    store: Store[str, list[str]] = Store("test")
    first, again = ["first"], ["again"]
    store.keep("a", first)
    store.keep("a", again)

    store.drop("a", first)
    assert store.get("a") is again
    store.drop("a", again)
    assert store.get("a") is None


def test_a_value_whose_making_fails_is_not_kept() -> None:
    store: Store[str, str] = Store("test", 4)

    def failing(others: list[tuple[str, str]]) -> str:
        raise ValueError("no such run")

    with pytest.raises(ValueError, match="no such run"):
        store.made_once("a", failing)

    assert store.values() == []
    assert store.made_once("a", _making("A")) == "A"


def test_everything_is_forgotten_at_once_the_stores_made_last_first(
    afresh: Callable[[], None],
) -> None:
    forgotten: list[str] = []
    runs: Store[str, str] = Store("runs", on_drop=lambda key, _: forgotten.append(key))
    playbacks: Store[str, str] = Store("playbacks", on_drop=lambda key, _: forgotten.append(key))
    runs.keep("run", "R")
    playbacks.keep("playback", "P", pinned=True)

    forget_everything()

    # The playbacks, which work days out from the runs, stop first.
    assert forgotten == ["playback", "run"]
    assert runs.values() == [] and playbacks.values() == []


def test_no_test_forgets_a_store_itself() -> None:
    # Only conftest's fixtures forget (`afresh`, `no_playbacks`), so that a
    # test's slate is clean however the suite is ordered.
    forgetting = [
        f"{path.name}:{number}"
        for path in sorted(TESTS.glob("test_*.py"))
        if path.name != Path(__file__).name
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if OWN_FORGETTING.search(line)
    ]
    assert forgetting == []


def test_a_run_being_made_holds_up_no_request_for_another_scenario(
    afresh: Callable[[], None],
) -> None:
    # A branch of a run whose air a long request is working out waits for
    # it to carry on; a request for another scenario's run does not wait.
    base = fields._climate_day("climate_box", "default", "default", (), (), ())
    branch_key = ("climate_box", "default", "default", (), (), ((3600.0, "heater", 1.0),))
    with ThreadPoolExecutor(max_workers=2) as pool:
        with base.house._working:
            branch = pool.submit(fields._climate_day, *branch_key)
            asked = threading.Event()
            for _ in range(int(WAIT_S / POLL_S)):
                if branch_key in fields.CLIMATE_RUNS or branch.done() or asked.wait(POLL_S):
                    break
            other = pool.submit(
                fields._climate_day, "climate_box", "default", "cold_spring_day", (), (), ()
            )
            other.result(timeout=WAIT_S)
        branch.result(timeout=WAIT_S)
