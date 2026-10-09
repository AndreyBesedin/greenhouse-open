"""Open doors and vents driven by the wind and the stack effect (P07.6).

Each open door or vent passes air according to the pressure across it:

- **wind:** the wind's dynamic pressure, ½ ρ v², times a pressure
  coefficient for the surface the opening lies on, by the angle between the
  way the wind comes from and the surface's outward face, after the AIVC's
  tables for low-rise buildings: positive facing the wind on a wall,
  negative to its lee and over a shallow roof;
- **stack:** air inside warmer than outside is lighter, so the pressure
  inside falls more slowly with height: an opening high up lets the warm
  air out, and one low down lets the cold in;
- **flow:** each opening passes Q = C_d A √(2 |Δp| / ρ) with the sign of its
  pressure difference, C_d = 0.6. The house's own pressure is the one at
  which as much air leaves as enters, found by bisection.

Each open opening also exchanges air both ways, as much in as out, by the
single-sided formulas: by the stack effect over its own height,
Q = C_d A / 3 √(g H ΔT / T), and by the wind's turbulence, Q = 0.025 A v,
whichever is the more (CIBSE AM10). An opening alone has only this.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.domain.envelope import SurfaceCategory
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site, bearing

DISCHARGE_COEFFICIENT: Final = 0.6
GRAVITY_M_S2: Final = 9.81
# Dry air's gas constant, J/(kg K), and the kelvin's offset from °C.
AIR_GAS_CONSTANT: Final = 287.05
KELVIN: Final = 273.15
PASCALS_PER_HPA: Final = 100.0
# Single-sided ventilation by the wind's turbulence: this share of the wind
# speed through the aperture.
TURBULENT_SHARE: Final = 0.025
# The stack's single-sided exchange through an opening's height.
STACK_THIRD: Final = 3.0
# Pressure coefficients by the angle between the wind and a surface's
# outward face, every 45° from facing it: a low-rise building's walls, and
# its shallow roof.
_ANGLES_DEG: Final = (0.0, 45.0, 90.0, 135.0, 180.0)
WALL_COEFFICIENTS: Final = (0.7, 0.35, -0.5, -0.4, -0.2)
ROOF_COEFFICIENTS: Final = (-0.7, -0.7, -0.6, -0.5, -0.4)
# The house's pressure is bisected this many times between its openings'.
BISECTIONS: Final = 60
HALF_TURN_DEG: Final = 180.0


@dataclass(frozen=True)
class OpeningSite:
    """Where an open door or vent is, for the pressure across it: its
    aperture (m²), its centre's height and its vertical extent (m), the
    compass bearing its surface faces out to, and whether it is in the
    roof."""

    opening_id: str
    aperture_m2: float
    height_m: float
    extent_m: float
    facing_deg: float
    roof: bool


class OpeningFlow(BaseModel):
    """What an open door or vent passes: its net flow into the house (m³/s,
    negative out), and what it exchanges each way besides."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    opening_id: str
    net_m3_s: float
    exchange_m3_s: float


class OpeningsAt(BaseModel):
    """What each open door and vent passes at a moment of a run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_s: float
    openings: list[OpeningFlow]


def opening_sites(envelope: Envelope, site: Site) -> dict[str, OpeningSite]:
    """Each of the envelope's open doors and vents, where it is, its facing
    on the Earth turned by the greenhouse's frame and the site's compass."""
    surfaces = {surface.surface_id: surface for surface in envelope.surfaces_in_world()}
    sites = {}
    for opening in envelope.openings:
        aperture = opening.aperture_area()
        if aperture <= 0:
            continue
        surface = surfaces[opening.surface_id]
        centre = surface.transform.apply(Vector3(x=opening.centre.x, y=opening.centre.y, z=0.0))
        up = surface.transform.rotation.rotate(Vector3(x=0.0, y=opening.height, z=0.0))
        inward = surface.transform.rotation.rotate(Vector3(x=0.0, y=0.0, z=1.0))
        outward = Vector3(x=-inward.x, y=-inward.y, z=0.0)
        sites[opening.opening_id] = OpeningSite(
            opening_id=opening.opening_id,
            aperture_m2=aperture,
            height_m=centre.z,
            extent_m=abs(up.z),
            facing_deg=site.bearing_of(outward),
            roof=surface.category == SurfaceCategory.ROOF,
        )
    return sites


def pressure_coefficient(opening: OpeningSite, wind_from_deg: float) -> float:
    """The wind's pressure coefficient at an opening, for a wind from a
    bearing: interpolated between the tables' angles."""
    angle = abs(bearing(wind_from_deg - opening.facing_deg + HALF_TURN_DEG) - HALF_TURN_DEG)
    table = ROOF_COEFFICIENTS if opening.roof else WALL_COEFFICIENTS
    step = _ANGLES_DEG[1]
    index = min(int(angle // step), len(_ANGLES_DEG) - 2)
    share = (angle - _ANGLES_DEG[index]) / step
    return (1.0 - share) * table[index] + share * table[index + 1]


def air_density_kg_m3(temperature_c: float, pressure_hpa: float) -> float:
    """Dry air's density at a temperature and pressure."""
    return pressure_hpa * PASCALS_PER_HPA / (AIR_GAS_CONSTANT * (temperature_c + KELVIN))


def single_sided_m3_s(opening: OpeningSite, inside_c: float, outside: WeatherState) -> float:
    """What an opening exchanges each way on its own: by the stack effect
    over its height, or by the wind's turbulence, whichever is the more."""
    mean_k = (inside_c + outside.air_temperature_c) / 2 + KELVIN
    difference = abs(inside_c - outside.air_temperature_c)
    stack = (
        DISCHARGE_COEFFICIENT
        * opening.aperture_m2
        / STACK_THIRD
        * math.sqrt(GRAVITY_M_S2 * opening.extent_m * difference / mean_k)
    )
    turbulence = TURBULENT_SHARE * opening.aperture_m2 * outside.wind_speed_m_s
    return max(stack, turbulence)


def opening_flows(
    openings: Sequence[OpeningSite], inside_c: float, outside: WeatherState
) -> list[OpeningFlow]:
    """What each open door and vent passes: the net flows the wind and the
    stack drive through them, as much leaving as entering, and what each
    exchanges on its own."""
    pressure = outside.barometric_pressure_hpa
    inside_rho = air_density_kg_m3(inside_c, pressure)
    outside_rho = air_density_kg_m3(outside.air_temperature_c, pressure)
    dynamic_pa = outside_rho * outside.wind_speed_m_s**2 / 2
    # The pressure outside each opening, less the inside's at the floor, but
    # for the house's own.
    driving = [
        pressure_coefficient(opening, outside.wind_direction_deg) * dynamic_pa
        + (inside_rho - outside_rho) * GRAVITY_M_S2 * opening.height_m
        for opening in openings
    ]

    def inflows(house_pa: float) -> list[float]:
        flows = []
        for opening, pushing in zip(openings, driving, strict=True):
            across = pushing - house_pa
            speed = math.sqrt(2 * abs(across) / outside_rho)
            flows.append(math.copysign(DISCHARGE_COEFFICIENT * opening.aperture_m2 * speed, across))
        return flows

    nets = [0.0] * len(openings)
    if len(openings) > 1 and max(driving) > min(driving):
        low, high = min(driving), max(driving)
        for _ in range(BISECTIONS):
            middle = (low + high) / 2
            if sum(inflows(middle)) > 0:
                low = middle
            else:
                high = middle
        nets = inflows((low + high) / 2)
        # What bisection leaves unbalanced is taken from the largest flow.
        largest = max(range(len(nets)), key=lambda index: abs(nets[index]))
        nets[largest] -= sum(nets)
    return [
        OpeningFlow(
            opening_id=opening.opening_id,
            net_m3_s=net,
            exchange_m3_s=single_sided_m3_s(opening, inside_c, outside),
        )
        for opening, net in zip(openings, nets, strict=True)
    ]
