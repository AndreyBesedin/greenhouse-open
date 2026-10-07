"""How a scenario's air is driven when a CFD solver solves it.

Air is blown in through the scenario's inlets, square to each, and let out
through every other open door and vent. The flow is steady and laminar, but
with an effective viscosity far above the air's own: the mesh's half-metre
cells are too coarse to resolve turbulence, so its mixing is folded into the
viscosity, as a constant eddy viscosity. The temperature is not solved: the
air is the same temperature everywhere.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt

# The air's density, which turns a solver's kinematic pressure into pascals.
AIR_DENSITY_KG_M3: Final = 1.2


class CfdSetup(BaseModel):
    """What drives a scenario's air in a CFD solve, and for how long."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The open doors and vents air is blown in through, by identifier; by
    # default, the first that is open. Every other open one lets it out.
    inlets: list[str] | None = None
    # How fast the air comes in, square to each inlet.
    inlet_speed_m_s: PositiveFloat = 0.5
    # The air's kinematic viscosity with what the mesh cannot resolve of its
    # turbulence: about 1.5e-5 m²/s for still air.
    effective_viscosity_m2_s: PositiveFloat = 0.01
    # The most iterations a solve may take before it stops, converged or not.
    iterations: PositiveInt = 2000
