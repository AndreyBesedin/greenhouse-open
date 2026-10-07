"""P01's final QA, `greenhouse-shell`, over many greenhouses: changing the
length, width, number of spans, bay spacing, eave and ridge heights and vent
opening leaves no gaps or inverted surfaces, and the dimensions right.

The browser side of the walkthrough is `web/e2e/greenhouse-shell.spec.ts`.
"""

import itertools
import math

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.envelope import OpeningKind, SurfaceCategory
from greenhouse_sim.scene.snapshot import SceneEntityKind, SceneSnapshot
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.envelope_checks import inverted_surfaces, outline, shared_edges
from greenhouse_sim.world.geometry import Point2

LENGTHS = (4.0, 24.0, 100.0)
WIDTHS = (3.2, 9.6, 48.0)
SPANS = (1, 2, 5)
BAYS = (1, 3, 25)
# Eave and ridge heights: pitched roofs of two rises, and a flat one.
HEIGHTS = ((3.0, 3.0), (4.0, 4.65), (6.0, 8.0))
VENT_OPENINGS = (0.0, 0.5, 1.0)


def _greenhouse(
    length: float, width: float, spans: int, bays: int, eave: float, ridge: float, vent: float
) -> Envelope:
    """A greenhouse of these dimensions, with a roof vent near its first ridge."""
    envelope = Envelope(
        length=length, width=width, eave_height=eave, ridge_height=ridge, spans=spans, bays=bays
    )
    slope = math.hypot(envelope.span_width / 2, ridge - eave)
    vent_depth = slope / 2
    return Envelope.model_validate(
        envelope.model_dump()
        | {
            "openings": [
                Opening(
                    opening_id="roof_vent_1",
                    kind=OpeningKind.ROOF_VENT,
                    surface_id="roof_1_right",
                    centre=Point2(x=0.0, y=slope / 2 - vent_depth / 2),
                    width=length / 2,
                    height=vent_depth,
                    opening=vent,
                )
            ]
        }
    )


GREENHOUSES = [
    _greenhouse(length, width, spans, bays, eave, ridge, vent)
    for (length, width, spans, bays, (eave, ridge), vent) in itertools.product(
        LENGTHS, WIDTHS, SPANS, BAYS, HEIGHTS, VENT_OPENINGS
    )
]


def _name(envelope: Envelope) -> str:
    return (
        f"{envelope.length:g}x{envelope.width:g}m-{envelope.spans}spans-{envelope.bays}bays-"
        f"{envelope.eave_height:g}to{envelope.ridge_height:g}m-vent{envelope.openings[0].opening:g}"
    )


@pytest.mark.parametrize("envelope", GREENHOUSES, ids=_name)
def test_the_shell_has_no_gaps_or_inverted_surfaces(envelope: Envelope) -> None:
    assert set(shared_edges(envelope).values()) == {2}
    assert inverted_surfaces(envelope) == []


@pytest.mark.parametrize("envelope", GREENHOUSES, ids=_name)
def test_the_shell_has_the_dimensions_it_was_given(envelope: Envelope) -> None:
    corners = [corner for surface in envelope.surfaces() for corner in outline(surface)]
    xs, ys, zs = zip(*corners, strict=True)
    walls = [s for s in envelope.surfaces() if s.surface_id.startswith("side_wall")]
    roofs = [s for s in envelope.surfaces() if s.category == SurfaceCategory.ROOF]

    assert (min(xs), max(xs)) == (0, envelope.length)
    assert (min(ys), max(ys)) == pytest.approx((0, envelope.width))
    assert (min(zs), max(zs)) == (0, envelope.ridge_height)
    assert all(max(z for _, _, z in outline(wall)) == envelope.eave_height for wall in walls)
    assert len(roofs) == 2 * envelope.spans
    assert len({member.frame for member in envelope.members()}) == envelope.bays + 1


@pytest.mark.parametrize("envelope", GREENHOUSES, ids=_name)
def test_the_shells_vent_opens_no_more_than_its_frame(envelope: Envelope) -> None:
    [vent] = envelope.openings
    area = vent.aperture_area()

    assert 0.0 <= area <= vent.width * vent.height
    assert (area == 0.0) == (vent.opening == 0.0)


def test_the_api_changes_the_shell_of_a_scenarios_greenhouse() -> None:
    """The browser walkthrough's greenhouse, as the API draws it."""
    query = "envelope=length:12,width:9.6,spans:3,bays:4,eave_height:4,ridge_height:4.8"
    response = respond("GET", f"/api/scenarios/gh_demo/scene?{query}&open=roof_vent_1:1")
    scene = SceneSnapshot.model_validate(response.body)
    kinds = [entity.kind for entity in scene.entities]
    [bounds] = [e for e in scene.entities if e.kind == SceneEntityKind.GREENHOUSE_BOUNDS]

    assert response.status == 200
    assert bounds.shape.model_dump() == {"shape": "box", "size_x": 12, "size_y": 9.6, "size_z": 4.8}
    assert kinds.count(SceneEntityKind.ROOF) == 6
    assert kinds.count(SceneEntityKind.FRAME) == 5 * (4 + 6)
