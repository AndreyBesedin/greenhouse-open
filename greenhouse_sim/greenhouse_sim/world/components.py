"""A house's components, described (P24.2, decision 0080): what its cover
is made of, what each wall faces, its floor and the soil under it, the
screens drawn across it, and the networks of pipes that heat it, in the
house's frame and in metres.

An installation holds them in a section of their own, `components`, beside
its envelope and layout (`HouseComponents`), and gives them to its
scenario's runs. A component left undescribed is left out of it, and a
house that describes none has no section: it is written as it was, and so
are its manifest and every run's identity.

A house air model that cannot model a described component refuses the
house, naming it (`HouseComponents.described`, read by `ScenarioConfig`),
as a run refuses rows of crops it cannot grow. Today's two, `grid` and
`whole_house`, model its cover alone: its sheets give their glass its U
(`climate.glazing`) and the sunlight its transmittance (`solar.glass`).
What models the rest comes with the multi-node climate (P24.3 on).
"""

from collections import Counter
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from greenhouse_sim.domain.components import Component, PipeKind, ScreenKind
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.materials import (
    COVER_MATERIALS,
    CoverChoice,
    CoverMaterial,
    FloorSurface,
    LayerChoice,
    ScreenChoice,
    material,
)
from greenhouse_sim.world.zones import EDGE_TOLERANCE_M, Strip

if TYPE_CHECKING:
    from greenhouse_sim.world.envelope import Envelope

# The envelope's walls, by their surfaces' identifiers (`Envelope.surfaces`).
type WallId = Literal["side_wall_right", "side_wall_left", "end_wall_front", "end_wall_back"]
# A neighbouring space's, or the deep soil's, temperature lies within an
# outside air's, as a recorded weather's file bounds it (`weather.recorded`).
COLDEST_C: Final = -60.0
WARMEST_C: Final = 60.0
# A neighbouring space's recorded temperature is a file of its own, named as
# a recorded weather's is: its name is part of every run's identity.
RECORDING_NAME_PATTERN: Final = r"^[a-z0-9][a-z0-9_.-]{0,95}\.csv$"

type Temperature = Annotated[float, Field(ge=COLDEST_C, le=WARMEST_C)]


def undescribed(component: object) -> bool:
    """Whether a house leaves a component out, so that it writes nothing."""
    return component is None


class _Component(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Cover(_Component):
    """What the cover is made of: the roof's slopes, all of one material,
    and each wall it names, of its own; the walls it does not name are of
    the roof's."""

    roof: CoverChoice
    walls: dict[WallId, CoverChoice] = {}

    def sheet(self, surface_id: str) -> CoverMaterial:
        """What a surface of the envelope is made of, by its identifier: a
        wall's own sheet, if it names one, and the roof's for the others
        and for each of the roof's slopes."""
        chosen = next(
            (sheet for wall, sheet in self.walls.items() if wall == surface_id), self.roof
        )
        return material(chosen, COVER_MATERIALS)


class OnTheOutside(_Component):
    """A wall on the outside air, as a wall is unless it says otherwise."""

    faces: Literal["outside"] = "outside"


class OnASpace(_Component):
    """A wall on a neighbouring space, a corridor, a headhouse or another
    house, at its temperature: constant, in °C, or recorded in a file of
    its own, which names it; one of the two."""

    faces: Literal["space"] = "space"
    kind: Literal["corridor", "headhouse", "house"]
    temperature_c: Annotated[Temperature | None, Field(exclude_if=undescribed)] = None
    recording: Annotated[
        str | None,
        Field(pattern=RECORDING_NAME_PATTERN, exclude_if=undescribed),
    ] = None

    @model_validator(mode="after")
    def _at_one_temperature(self) -> Self:
        if (self.temperature_c is None) == (self.recording is None):
            raise ValueError("a space is at a temperature_c or a recording of it, one of the two")
        return self


class OnNothing(_Component):
    """A wall no heat crosses."""

    faces: Literal["nothing"] = "nothing"


# What a wall faces, told apart by `faces`.
type WallBoundary = Annotated[OnTheOutside | OnASpace | OnNothing, Field(discriminator="faces")]


class FloorLayer(_Component):
    """A layer of the floor, or of the soil under it: its thickness, in
    metres, and what it is made of."""

    thickness_m: PositiveFloat
    material: LayerChoice


class Floor(_Component):
    """The floor, from its surface down: the surface's optics, its layers,
    the first the floor's own and those under it the soil's, and the deep
    soil's temperature under the last, in °C."""

    surface: FloorSurface
    layers: list[FloorLayer] = Field(min_length=1)
    deep_soil_temperature_c: Temperature

    @property
    def depth_m(self) -> float:
        """How deep its layers go, from the surface to the deep soil."""
        return sum(layer.thickness_m for layer in self.layers)


class Screen(_Component):
    """A screen drawn across the house: what it is for, its cloth, the
    height it is drawn at above the floor, the eaves at most, the floor it
    covers, the whole house's if it names none, and how far it is drawn as
    the run starts, from 0 (open) to 1 (closed). Commands and a screen
    loop are to drive it, as they drive a vent (P24.4)."""

    screen_id: ItemId
    kind: ScreenKind
    material: ScreenChoice
    height_m: PositiveFloat
    extent: Annotated[Strip | None, Field(exclude_if=undescribed)] = None
    closure: float = Field(default=0.0, ge=0.0, le=1.0)


class PipeNetwork(_Component):
    """A network of heating pipes: where it runs, all its pipes' length end
    to end, their outer and inner diameters, their height above the floor,
    the eaves at most, and their longwave emissivity. Its heat leaves them
    by convection to the air and by radiation to what they see, as the
    model that heats them works out (P24.8)."""

    network_id: ItemId
    kind: PipeKind
    length_m: PositiveFloat
    outer_diameter_m: PositiveFloat
    inner_diameter_m: PositiveFloat
    height_m: NonNegativeFloat
    longwave_emissivity: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _hollow(self) -> Self:
        if self.inner_diameter_m >= self.outer_diameter_m:
            raise ValueError(
                f"its inner diameter, {self.inner_diameter_m:g} m, is not inside its outer,"
                f" {self.outer_diameter_m:g} m"
            )
        return self


# Lists and maps of components hold at least one: none is left out.
type Boundaries = Annotated[dict[WallId, WallBoundary], Field(min_length=1)]
type Screens = Annotated[list[Screen], Field(min_length=1)]
type PipeNetworks = Annotated[list[PipeNetwork], Field(min_length=1)]


class HouseComponents(_Component):
    """What a house is made of and has beyond its envelope and layout, each
    left out while undescribed: its cover's materials; what each wall it
    names faces, the others facing the outside; its floor; the screens
    drawn across it; and its networks of heating pipes. It describes one at
    least: a house that describes none has no section of them. Its screens
    and pipe networks are each named apart, as a command names one."""

    cover: Annotated[Cover | None, Field(exclude_if=undescribed)] = None
    boundaries: Annotated[Boundaries | None, Field(exclude_if=undescribed)] = None
    floor: Annotated[Floor | None, Field(exclude_if=undescribed)] = None
    screens: Annotated[Screens | None, Field(exclude_if=undescribed)] = None
    pipe_networks: Annotated[PipeNetworks | None, Field(exclude_if=undescribed)] = None

    @model_validator(mode="after")
    def _describes_one_at_least(self) -> Self:
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("it describes no component: a house without one leaves it out")
        return self

    @model_validator(mode="after")
    def _named_apart(self) -> Self:
        repeated = sorted(name for name, count in Counter(self.names()).items() if count > 1)
        if repeated:
            raise ValueError(f"screens or pipe networks share an identifier: {', '.join(repeated)}")
        return self

    def names(self) -> list[str]:
        """What its screens and pipe networks are called."""
        return [screen.screen_id for screen in self.screens or []] + [
            network.network_id for network in self.pipe_networks or []
        ]

    def outside(self, envelope: Envelope) -> list[str]:
        """What of it does not fit in the house `envelope` encloses: a screen
        above the eaves, or over more than the floor, and a pipe network above
        the eaves."""
        screens = [
            screen.screen_id
            for screen in self.screens or []
            if screen.height_m > envelope.eave_height
            or not all(
                -EDGE_TOLERANCE_M <= corner.x <= envelope.length + EDGE_TOLERANCE_M
                and -EDGE_TOLERANCE_M <= corner.y <= envelope.width + EDGE_TOLERANCE_M
                for corner in ([] if screen.extent is None else screen.extent.corners())
            )
        ]
        networks = [
            network.network_id
            for network in self.pipe_networks or []
            if network.height_m > envelope.eave_height
        ]
        return screens + networks

    def described(self) -> list[tuple[Component, str]]:
        """Each component it describes that today's house has not, what it
        is and its name, for a model to refuse by: its cover, each wall on a
        space or on nothing, its floor, each screen and each pipe network. A
        wall on the outside is today's, and is not listed."""
        described: list[tuple[Component, str]] = []
        if self.cover is not None:
            described.append((Component.COVER, "its cover's materials"))
        for wall, boundary in (self.boundaries or {}).items():
            if isinstance(boundary, OnASpace):
                described.append((Component.WALL_ON_A_SPACE, f"{wall} on a {boundary.kind}"))
            elif isinstance(boundary, OnNothing):
                described.append((Component.WALL_ON_NOTHING, f"{wall} on nothing"))
        if self.floor is not None:
            described.append((Component.FLOOR, "its floor"))
        described += [
            (Component.SCREEN, f"the {screen.kind} screen {screen.screen_id}")
            for screen in self.screens or []
        ]
        described += [
            (Component.PIPE_NETWORK, f"the {network.kind} pipes {network.network_id}")
            for network in self.pipe_networks or []
        ]
        return described
