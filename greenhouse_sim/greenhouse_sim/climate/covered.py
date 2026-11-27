"""A climate run's house as its air beside its cover and the sky (P24.3,
decision 0078): the house air's `vanthoor` model, its nodes and their
equations those of `climate.vanthoor`.

It is the whole house (`climate.house`) in all but how its air goes
through a stretch: its loops, its switches, its stretches, what it keeps
and takes over, and its means are the whole house's. Where the whole house
exchanges heat with the outside through its glass's U, this house's air
gives it to its cover's inside layers, which pass it to their outside
layers, the outside air and the sky; and what condenses, condenses on the
cover's inside, as well as beyond saturation in the air.

- **Its geometry is the envelope's:** its air the envelope's own volume,
  its cover each wall's and roof slope's own area, not their projection,
  and its floor the envelope's.
- **Its cover's sheets are the described cover's,** surface by surface,
  each glass its walls and roof are of one pair of layers; or single glass
  throughout, its sheet's resistance its glass's, where no cover is
  described.
- **Its cover's layers start** at the air's temperature, and settle in
  seconds as their heat is little.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields

import numpy as np
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.glazing import Glass, HouseGlass
from greenhouse_sim.climate.house import (
    FEWEST_SAMPLES,
    HUMIDITY_EDGE_S,
    STEP_S,
    Course,
    HouseAir,
    WholeHouse,
    _outside_water_g_kg,
    _Steady,
)
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg, saturation_ratio_g_kg
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.sky import sky_temperature_c
from greenhouse_sim.climate.vanthoor import (
    AIR,
    CONDENSED,
    WATER,
    Held,
    HouseNodes,
    Layers,
    NodesCourse,
)
from greenhouse_sim.domain.envelope import SurfaceCategory
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.components import Cover
from greenhouse_sim.world.envelope import Envelope, outline
from greenhouse_sim.world.materials import UNDESCRIBED_SHEET, CoverMaterial

# Each glass's inside and outside layers' temperatures, °C.
type CoverTemperatures = tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class CoveredAir(HouseAir):
    """The house's air at a moment (`climate.house.HouseAir`), with its
    cover's layers then: each glass's inside and outside, °C, in the order
    of its nodes' layers."""

    cover_c: CoverTemperatures = ()


def covered(air: HouseAir, cover_c: CoverTemperatures) -> CoveredAir:
    """`air`, its cover's layers at `cover_c`."""
    return CoveredAir(
        **{each.name: getattr(air, each.name) for each in fields(HouseAir)}, cover_c=cover_c
    )


def plain(air: HouseAir) -> HouseAir:
    """`air` alone, without what its model keeps beside it."""
    return HouseAir(**{each.name: getattr(air, each.name) for each in fields(HouseAir)})


class HouseNodesState(BaseModel):
    """What a checkpoint keeps of a covered house's model beside its air
    (decision 0055): its cover's layers on the checkpoint's day, and an hour
    before it where the checkpoint keeps its air then, each glass's inside
    and outside, °C."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cover_c: CoverTemperatures
    cover_before_c: CoverTemperatures | None = None


def kept_nodes(air: HouseAir, before: HouseAir | None) -> HouseNodesState | None:
    """What a checkpoint keeps of the house's nodes beside `air` and the air
    `before` it, if it keeps the air then: none beside a house's air
    alone."""
    if not isinstance(air, CoveredAir):
        return None
    return HouseNodesState(
        cover_c=air.cover_c,
        cover_before_c=before.cover_c if isinstance(before, CoveredAir) else None,
    )


def restored(air: HouseAir, kept: object, *, before: bool = False) -> HouseAir:
    """`air` as a checkpoint keeps it, beside the nodes its house air's model
    keeps with it (`kept`, its state), on its day or `before` it, if it
    keeps them: `air` alone otherwise."""
    if not isinstance(kept, HouseNodesState):
        return air
    cover = kept.cover_before_c if before else kept.cover_c
    return air if cover is None else covered(air, cover)


def _area_m2(points: Sequence[tuple[float, float]]) -> float:
    """A flat polygon's area, by its corners in order."""
    twice = sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]], strict=True)
    )
    return abs(twice) / 2


def envelope_volume_m3(envelope: Envelope) -> float:
    """The air the envelope holds: its walls' height over its floor, and
    each span's roof above its eaves, a triangle across the span."""
    roof_m2 = envelope.span_width * (envelope.ridge_height - envelope.eave_height) / 2
    across_m2 = envelope.width * envelope.eave_height + envelope.spans * roof_m2
    return envelope.length * across_m2


def house_nodes(envelope: Envelope, cover: Cover | None, glass: HouseGlass) -> HouseNodes:
    """A house's nodes over its envelope, its cover of the sheets `cover`
    describes, or of single glass of each surface's `glass` where it
    describes none (see the module)."""
    areas: dict[tuple[Glass, CoverMaterial], float] = {}
    for surface in envelope.surfaces():
        if surface.category == SurfaceCategory.FLOOR:
            continue
        sheet = UNDESCRIBED_SHEET if cover is None else cover.sheet(surface.surface_id)
        key = (glass.of(surface.surface_id), sheet)
        corners = [(point.x, point.y) for point in outline(surface.shape)]
        areas[key] = areas.get(key, 0.0) + _area_m2(corners)
    layers = [
        Layers.of(sheet, area, sheet_m2k_w=its.sheet_m2k_w if cover is None else None)
        for (its, sheet), area in areas.items()
    ]
    return HouseNodes(
        volume_m3=envelope_volume_m3(envelope),
        floor_m2=envelope.length * envelope.width,
        layers=layers,
    )


class _CoveredCourse:
    """How a covered house's air goes through a stretch, as its nodes go
    (`climate.vanthoor.NodesCourse`), read as the whole house reads a
    course (`climate.house.Course`)."""

    def __init__(self, nodes: NodesCourse, venting_s: float, outside_g_kg: float) -> None:
        self.nodes = nodes
        self.venting_s = venting_s
        self.outside_g_kg = outside_g_kg
        self._rising_c_s = float(nodes.nodes.rates(nodes.start, nodes.held)[AIR])

    def temperature_c(self, start_c: float, duration_s: float) -> float:
        return float(self.nodes.at(duration_s)[AIR])

    def water_g_kg(self, start_g_kg: float, duration_s: float) -> float:
        return float(self.nodes.at(duration_s)[WATER])

    def heads(self, start_c: float, *, up: bool) -> bool:
        return self._rising_c_s > 0 if up else self._rising_c_s < 0

    def _crossing_s(
        self, beyond: Callable[[np.ndarray], float], within_s: float, *, up: bool | None = None
    ) -> float | None:
        return self.nodes.crossing_s(
            beyond, within_s, samples=FEWEST_SAMPLES, edge_s=HUMIDITY_EDGE_S, up=up
        )

    def reaching_s(self, start_c: float, edge_c: float) -> float | None:
        if start_c == edge_c:
            return 0.0
        return self._crossing_s(lambda state: float(state[AIR]) - edge_c, self.nodes.horizon_s)

    def held_water_reaching_s(
        self, start_c: float, start_g_kg: float, edge_g_kg: float, within_s: float, *, up: bool
    ) -> float | None:
        def beyond(state: np.ndarray) -> float:
            water = max(float(state[WATER]), 0.0)
            return min(water, float(saturation_ratio_g_kg(float(state[AIR])))) - edge_g_kg

        return self._crossing_s(beyond, within_s, up=up)

    def humidity_reaching_s(
        self, start_c: float, start_g_kg: float, edge_pct: float, within_s: float, *, up: bool
    ) -> float | None:
        def beyond(state: np.ndarray) -> float:
            holds = float(humidity_ratio_g_kg(float(state[AIR]), edge_pct))
            return float(state[WATER]) - holds

        return self._crossing_s(beyond, within_s, up=up)


class CoveredHouse(WholeHouse):
    """A climate run's house as its air beside its cover, of `nodes`, and
    the sky, as `sky` gives its temperature under the weather: see the
    module."""

    def __init__(
        self,
        run: ClimateRun,
        nodes: HouseNodes,
        sky: Callable[[WeatherState], float] = sky_temperature_c,
    ) -> None:
        super().__init__(run)
        self.nodes = nodes
        self.volume_m3 = nodes.volume_m3
        self._sky = sky
        first = self._kept[0.0]
        start_c = first.temperature_c
        self._kept[0.0] = covered(first, ((start_c, start_c),) * len(nodes.layers))

    def refusal(self, air: HouseAir) -> str | None:
        """Why `air` could not be this house's at a moment, or None if it
        could: air beside a cover of as many glasses as its own."""
        glasses = len(self.nodes.layers)
        if not isinstance(air, CoveredAir):
            return f"its house keeps its air beside a cover of {glasses} glasses, and keeps none"
        if len(air.cover_c) != glasses:
            return f"its house's cover is of {glasses} glasses, not {len(air.cover_c)}"
        return None

    def _cover_of(self, air: HouseAir) -> CoverTemperatures:
        """`air`'s cover's layers: refused if it is not air beside this
        house's cover."""
        refused = self.refusal(air)
        if refused is not None or not isinstance(air, CoveredAir):
            raise ValueError(refused)
        return air.cover_c

    def seed(self, moment_s: float, air: HouseAir) -> None:
        """Take `air`, beside this house's cover, as its air at `moment_s`
        (`WholeHouse.seed`)."""
        self._cover_of(air)
        super().seed(moment_s, air)

    def _course(
        self,
        air: HouseAir,
        steady: _Steady,
        outside: WeatherState,
        time_s: float,
        sun_w: float = 0.0,
    ) -> Course:
        """How the air and its cover go from `air` through a stretch of at
        most `STEP_S`, at steady levels, under the weather `outside`, its
        doors and vents open as they are at `time_s`."""
        venting_m3_s = self._venting_m3_s(air, outside, time_s)
        held = Held(
            outside_c=outside.air_temperature_c,
            outside_g_kg=_outside_water_g_kg(outside),
            wind_m_s=outside.wind_speed_m_s,
            sky_c=self._sky(outside),
            air_heat_w=steady.heat_w + sun_w,
            sun_on_floor_w=outside.global_radiation_w_m2 * self.nodes.floor_m2,
            exchanged_m3_s=venting_m3_s,
            drying_kg_s=steady.water_removed_kg_s,
        )
        state = self.nodes.state(air.temperature_c, air.humidity_g_kg, self._cover_of(air))
        return _CoveredCourse(
            self.nodes.course(state, held, STEP_S),
            venting_s=venting_m3_s / self.volume_m3,
            outside_g_kg=held.outside_g_kg,
        )

    def _advance(
        self,
        air: HouseAir,
        steady: _Steady,
        outside: WeatherState,
        duration_s: float,
        time_s: float,
        *,
        sun_w: float = 0.0,
        course: Course | None = None,
    ) -> HouseAir:
        course = course or self._course(air, steady, outside, time_s, sun_w)
        if not isinstance(course, _CoveredCourse):
            raise TypeError("a covered house's air goes by its nodes")
        end = course.nodes.at(duration_s)
        after = self._after(
            air,
            steady,
            outside,
            duration_s=duration_s,
            course=course,
            temperature=float(end[AIR]),
            water=float(end[WATER]),
        )
        on_cover_kg = float(end[CONDENSED])
        if not math.isfinite(on_cover_kg):
            raise ValueError("a covered house's air went beyond what it can hold")
        return covered(
            HouseAir(
                **{
                    each.name: getattr(after, each.name)
                    for each in fields(HouseAir)
                    if each.name != "condensed_kg"
                },
                condensed_kg=after.condensed_kg + on_cover_kg,
            ),
            self.nodes.layers_c(end),
        )
