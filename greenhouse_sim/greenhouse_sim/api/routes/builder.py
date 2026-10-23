"""The setup builder (P12): the installations' drafts, kept, revised and
run (decision 0051), a first draft from its first form, an edit assessed and
drawn before it is saved, and a scenario's house to copy.

    GET /api/drafts                       the installations' drafts kept, each
                                          at its latest revision (P12.1,
                                          decision 0051)
    GET /api/drafts/{id}                  one, its installation and what stops
                                          it running; ?revision=2 an earlier
                                          revision
    GET /api/drafts/{id}/revisions        its revisions, the first first
    POST /api/drafts/{id}/save?on=3       an installation's file, the body,
                                          saved as its next revision, made on
                                          revision 3; without on, a new draft
    POST /api/drafts/{id}/revert?revision=1&on=3
                                          an earlier revision saved again as
                                          its latest
    POST /api/drafts/{id}/delete?on=3     forgotten with its revisions
    POST /api/drafts/{id}/run?revision=2  run as a scenario of its own, with
                                          its period, site, seed and weather
                                          as the body gives them, registered
                                          and listed with the others

    GET /api/scenarios/{id}/installation  a scenario's house as an
                                          installation, assessed, for the
                                          builder to copy (P12.2)
    POST /api/builder/basic               a first draft from the builder's
                                          first form's values, the body,
                                          assessed (P12.2)
    POST /api/builder/assess              an installation's file, the body,
                                          read and assessed as it stands
    POST /api/builder/scene               the house an installation's file,
                                          the body, describes, as a scene

A change to a draft made on a revision that is no longer its latest is
refused as a conflict (409), as is a draft's run under a scenario's name
already taken. The first form's values and an installation's file are
refused (400) with `problems` beside the `error`: each field at fault, by
its path, and what is wrong with it.
"""

from typing import Final

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, json_body, last, text_body
from greenhouse_sim.services import builder, drafts
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.simulator import Simulator

# The largest revision a query may name: the largest whole number a draft's
# store keeps (SQLite's).
MOST_REVISION: Final = 2**63 - 1


def get(simulator: Simulator, segments: list[str], query: Query) -> Response | None:
    match segments:
        case ["api", "drafts"]:
            return answer(lambda: drafts.drafts(simulator))
        case ["api", "drafts", draft_id]:
            return answer(lambda: drafts.draft(simulator, draft_id, _revision(query, "revision")))
        case ["api", "drafts", draft_id, "revisions"]:
            return answer(lambda: drafts.revisions(simulator, draft_id))
        case ["api", "scenarios", scenario_id, "installation"]:
            return answer(lambda: builder.scenario_house(simulator.catalogue, scenario_id))
        case _:
            return None


def post(simulator: Simulator, segments: list[str], query: Query, body: bytes) -> Response | None:
    match segments:
        case ["api", "builder", "basic"]:
            return answer(lambda: builder.basic(json_body(body)))
        case ["api", "builder", "assess"]:
            return answer(lambda: builder.assess(text_body(body)))
        case ["api", "builder", "scene"]:
            return answer(lambda: builder.scene(text_body(body)))
        case ["api", "drafts", draft_id, "save"]:
            return answer(
                lambda: drafts.save(simulator, draft_id, text_body(body), _revision(query, "on"))
            )
        case ["api", "drafts", draft_id, "revert"]:
            return answer(
                lambda: drafts.revert(
                    simulator, draft_id, _named(query, "revision"), _named(query, "on")
                )
            )
        case ["api", "drafts", draft_id, "delete"]:
            return answer(lambda: drafts.delete(simulator, draft_id, _named(query, "on")))
        case ["api", "drafts", draft_id, "run"]:
            return answer(
                lambda: drafts.run(
                    simulator, draft_id, _revision(query, "revision"), json_body(body)
                )
            )
        case _:
            return None


def _revision(query: Query, name: str) -> int | None:
    """The revision a query names by `name`, a whole number from 1; None if
    it names none."""
    text = last(query, name)
    if text is None:
        return None
    # Its digits counted before they are read: a number too long to read,
    # or to keep, is refused as any other.
    whole = text.isascii() and text.isdigit() and len(text) <= len(str(MOST_REVISION))
    if not whole or not 1 <= int(text) <= MOST_REVISION:
        raise InvalidRequest(
            f"{name} is a revision, a whole number from 1 to {MOST_REVISION}, not {text!r}"
        )
    return int(text)


def _named(query: Query, name: str) -> int:
    """The revision a query must name by `name`."""
    revision = _revision(query, name)
    if revision is None:
        raise InvalidRequest(f"the request names no revision as {name}")
    return revision
