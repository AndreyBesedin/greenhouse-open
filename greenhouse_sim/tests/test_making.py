"""A kept value made once, outside its store's lock (AUDIT.29): requests for
it wait for the one that makes it, requests for anything else do not, and
a value whose making fails is not kept."""

import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest

from greenhouse_sim.services import fields
from greenhouse_sim.services.making import Kept, kept_values, made_once

# Long enough for a thread that is not stalled to finish.
WAIT_S = 5.0
POLL_S = 0.01


def _store() -> tuple[Kept[str, str], threading.Lock]:
    return OrderedDict(), threading.Lock()


def _making(value: str) -> Callable[[list[tuple[str, str]]], str]:
    """Makes `value`, whatever is kept."""
    return lambda others: value


def test_a_value_is_made_once_and_given_to_everyone_who_asks() -> None:
    kept, keeping = _store()
    started, finish = threading.Event(), threading.Event()
    made: list[str] = []

    def make(others: list[tuple[str, str]]) -> str:
        made.append("a")
        started.set()
        finish.wait(WAIT_S)
        return "A"

    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(made_once, kept, keeping, "a", 4, lambda key: True, make)
        assert started.wait(WAIT_S)
        others = [
            pool.submit(made_once, kept, keeping, "a", 4, lambda key: True, make) for _ in range(3)
        ]
        finish.set()
        assert [first.result(), *(other.result() for other in others)] == ["A"] * 4
    assert made == ["a"]


def test_making_one_value_holds_up_no_other() -> None:
    kept, keeping = _store()
    finish = threading.Event()

    def slow(others: list[tuple[str, str]]) -> str:
        finish.wait(WAIT_S)
        return "A"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(made_once, kept, keeping, "a", 4, lambda key: False, slow)
        other = made_once(kept, keeping, "b", 4, lambda key: False, lambda others: "B")
        assert other == "B"
        assert not first.done()
        finish.set()
        assert first.result() == "A"


def test_a_value_is_made_from_the_related_values_kept_before_it() -> None:
    kept, keeping = _store()
    for key in ("a1", "b1"):
        made_once(kept, keeping, key, 4, lambda other: False, _making(key.upper()))
    seen: list[list[tuple[str, str]]] = []

    def make(others: list[tuple[str, str]]) -> str:
        seen.append(others)
        return "A2"

    made_once(kept, keeping, "a2", 4, lambda other: other.startswith("a"), make)

    assert seen == [[("a1", "A1")]]
    assert kept_values(kept, keeping) == [("a1", "A1"), ("b1", "B1"), ("a2", "A2")]


def test_the_latest_values_are_kept_up_to_the_bound() -> None:
    kept, keeping = _store()
    for key in ("a", "b", "c"):
        made_once(kept, keeping, key, 2, lambda other: False, _making(key))
    made_once(kept, keeping, "b", 2, lambda other: False, lambda others: "again")

    assert kept_values(kept, keeping) == [("c", "c"), ("b", "b")]


def test_a_value_whose_making_fails_is_not_kept() -> None:
    kept, keeping = _store()

    def failing(others: list[tuple[str, str]]) -> str:
        raise ValueError("no such run")

    with pytest.raises(ValueError, match="no such run"):
        made_once(kept, keeping, "a", 4, lambda other: False, failing)

    assert kept_values(kept, keeping) == []
    assert made_once(kept, keeping, "a", 4, lambda other: False, lambda others: "A") == "A"


def test_a_run_being_made_holds_up_no_request_for_another_scenario() -> None:
    # A branch of a run whose air a long request is working out waits for
    # it to carry on; a request for another scenario's run does not wait.
    fields.forget_climate_runs()
    base = fields._climate_day("climate_box", "default", "default", (), (), ())
    branch_key = ("climate_box", "default", "default", (), (), ((3600.0, "heater", 1.0),))
    with ThreadPoolExecutor(max_workers=2) as pool:
        with base.house._working:
            branch = pool.submit(fields._climate_day, *branch_key)
            asked = threading.Event()
            for _ in range(int(WAIT_S / POLL_S)):
                if branch_key in fields._KEPT or branch.done() or asked.wait(POLL_S):
                    break
            other = pool.submit(
                fields._climate_day, "climate_box", "default", "cold_spring_day", (), (), ()
            )
            other.result(timeout=WAIT_S)
        branch.result(timeout=WAIT_S)
