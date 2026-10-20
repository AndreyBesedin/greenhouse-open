"""The table of routes at the top of `greenhouse_sim.api.routes`, and the
live commands' in `control`, say what the API answers (audit W14,
`AUDIT.16`): every route they list is one the code answers, with that
method, and every route the code answers is listed.

The tables are written by hand, for a reader; this holds them to the
`match` arms of `respond` and `live_stream` (GET), and `_posted` and
`control` (POST). A path's `{…}` is a segment a route captures, a query
after `?` is an example, `/play, /pause` lists two routes beside each
other, and a path ending in `/...` points to another table.
"""

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api import routes

SOURCE: Final = Path(routes.__file__).read_text()
# The functions whose `match` arms are routes, and the method each answers.
ROUTING: Final = {"respond": "GET", "live_stream": "GET", "_posted": "POST", "control": "POST"}
# A table's line: its method, its path, and what follows it.
LISTED: Final = re.compile(r"^\s+(GET|POST) (/api/\S+)(.*)$")
# A route listed beside the one before it: `, /pause`.
BESIDE: Final = re.compile(r"\s*,?\s*/([\w-]+),?")
# A path that points to another table.
ELSEWHERE: Final = "..."

type Segments = tuple[str | None, ...]


def _routes_answered() -> set[tuple[str, Segments]]:
    """Each route a `match` arm answers: its method, and its segments, None
    where it captures one."""
    answered: set[tuple[str, Segments]] = set()
    for node in ast.parse(SOURCE).body:
        if not isinstance(node, ast.FunctionDef) or node.name not in ROUTING:
            continue
        for match in (each for each in ast.walk(node) if isinstance(each, ast.Match)):
            for case in match.cases:
                if isinstance(case.pattern, ast.MatchSequence):
                    answered.add((ROUTING[node.name], _segments(case.pattern)))
    return answered


def _segments(pattern: ast.MatchSequence) -> Segments:
    segments: list[str | None] = []
    for part in pattern.patterns:
        if isinstance(part, ast.MatchValue) and isinstance(part.value, ast.Constant):
            segments.append(str(part.value.value))
        elif isinstance(part, ast.MatchAs) and part.pattern is None and part.name is not None:
            segments.append(None)
        else:
            raise AssertionError(f"a route's pattern this test cannot read: {ast.dump(part)}")
    return tuple(segments)


def _routes_listed() -> set[tuple[str, tuple[str, ...]]]:
    """Each route the tables list: its method, and its path's segments."""
    tables = [routes.__doc__ or "", routes.control.__doc__ or ""]
    listed: set[tuple[str, tuple[str, ...]]] = set()
    for line in (line for table in tables for line in table.splitlines()):
        found = LISTED.match(line)
        if found is None:
            continue
        method, path, rest = found.groups()
        segments = tuple(path.split("?")[0].rstrip(",").strip("/").split("/"))
        if segments[-1] == ELSEWHERE:
            continue
        listed.add((method, segments))
        while (beside := BESIDE.match(rest)) is not None:
            listed.add((method, (*segments[:-1], beside.group(1))))
            rest = rest[beside.end() :]
    return listed


def _answers(listed: tuple[str, ...], arm: Segments) -> bool:
    """Whether an arm answers a path as listed: each segment the same, or
    captured, and a listed `{…}` only where the arm captures."""
    return len(listed) == len(arm) and all(
        part is None if segment.startswith("{") else part in (None, segment)
        for segment, part in zip(listed, arm, strict=True)
    )


ANSWERED: Final = _routes_answered()
LISTED_ROUTES: Final = _routes_listed()


def test_the_tables_and_the_code_have_routes_to_compare() -> None:
    assert len(ANSWERED) > 30
    assert len(LISTED_ROUTES) > 30


def _in_order(route: tuple[str, Segments]) -> tuple[str, list[str]]:
    method, arm = route
    return method, [part or "" for part in arm]


def _named(part: object) -> str:
    """A test's name for a method, or for an arm's segments."""
    if isinstance(part, tuple):
        return "/".join(segment or "{}" for segment in part)
    return str(part)


@pytest.mark.parametrize(("method", "path"), sorted(LISTED_ROUTES), ids=_named)
def test_each_route_listed_is_answered(method: str, path: tuple[str, ...]) -> None:
    assert any(m == method and _answers(path, arm) for m, arm in ANSWERED), (
        f"{method} /{'/'.join(path)} is listed, and no route answers it"
    )


ANSWERED_IN_ORDER: Final = sorted(ANSWERED, key=_in_order)


@pytest.mark.parametrize(("method", "arm"), ANSWERED_IN_ORDER, ids=_named)
def test_each_route_answered_is_listed(method: str, arm: Segments) -> None:
    assert any(m == method and _answers(path, arm) for m, path in LISTED_ROUTES), (
        f"{method} /{'/'.join(p or '{…}' for p in arm)} is answered, and no table lists it"
    )


def test_a_route_left_out_of_the_table_is_found() -> None:
    """A check that cannot fail is worth nothing."""
    timeline = ("GET", ("api", "scenarios", "{id}", "timeline"))
    without = LISTED_ROUTES - {timeline}

    assert timeline in LISTED_ROUTES
    assert not any(
        m == "GET" and _answers(path, ("api", "scenarios", None, "timeline")) for m, path in without
    )
