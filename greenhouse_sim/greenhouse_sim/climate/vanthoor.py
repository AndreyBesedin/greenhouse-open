"""The house's air beside its cover and the sky (P24.3, decision 0078): the
nodes of the house air's `vanthoor` model, and how heat and water move
between them, after Vanthoor (2011, chapter 8) as GreenLight 2.0.7 writes
it (Katzin 2021). Its equations are written from them, not ported.

- **Its nodes:** the inside air, its temperature and the water it holds;
  and, for each glass the walls and roof are of, the cover's inside and
  outside layers (Vanthoor's eqs 8.7 and 8.8), each holding a tenth of its
  sheet's heat capacity (eqs 8.18 and 8.21). The CO₂ is carried as the whole
  house carries it, by the air exchanged.
- **Its boundaries:** the outside air and the sky, a black body at the
  sky's temperature (Table 8.1, ε_sky = 1).
- **Its fluxes,** each the house's, in W:
  - the air and the cover's inside, by free convection, `cHecIn |ΔT|^0.33`
    per K and m² of cover (eq 8.40, Table 8.4), or a film of a constant
    coefficient, where one is given (`Films`);
  - through the sheet, by its conduction, λ / h per m² of cover (eq 8.19);
  - the cover's outside and the outside air, `a + b v^c` per K and m² of
    cover in a wind v (Table 8.4: 2.8, 1.2 and 1), or another such law;
  - the cover's outside and the sky, `ε sigma (T⁴ - T_sky⁴)` over the house's
    floor, as GreenLight takes it (eq 8.38, its view factor 1 per m² of
    floor), shared among the glasses by their area;
  - the sun the cover absorbs, on its outside layer, over the floor (eq
    8.37), shared as the sky is;
  - the water condensing from the air on each glass's inside (eqs 8.43 and
    8.44), its latent heat given to it (eq 8.42);
  - the air exchanged with the outside, and the heat and the water the
    equipment and the sun give the air or take from it, as the whole house
    works them out, held through a stretch (`Held`).
- **Where it departs from GreenLight:** its air is one node, with no top
  compartment above an absent screen; conduction and heat capacity are per
  m² of the cover's own area, not of the floor; the saturation pressure is
  Buck's, as the rest of the simulator's (`climate.psychrometrics`); and
  its air's heat capacity and density are the whole house's.
- **A stretch is solved exactly** once its equations are linearised about
  its start, by the matrix exponential (`climate.exponential`); a piece of
  it is halved while the linearised rates at its end stray from the
  equations' by more than `STRAYS`, a small share of a degree or a gram
  over the piece.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from greenhouse_sim.climate.exponential import matrix_exponential
from greenhouse_sim.climate.psychrometrics import (
    ATMOSPHERE_PA,
    WATER_PER_AIR_G_KG,
    saturation_pressure_pa,
)
from greenhouse_sim.climate.transport import AIR_HEAT_CAPACITY_J_KG_K, GRAMS_PER_KG
from greenhouse_sim.units import AIR_DENSITY_KG_M3, KELVIN, STEFAN_BOLTZMANN_W_M2K4
from greenhouse_sim.world.materials import CoverMaterial

# Vanthoor (2011), Table 8.1.
LATENT_HEAT_J_KG: Final = 2.45e6
# Table 8.4: free convection between the air and the cover's inside,
# cHecIn |ΔT|^0.33 per K and m² of cover (W m⁻² K⁻¹·³³).
FREE_CONVECTION: Final = 1.86
FREE_CONVECTION_POWER: Final = 0.33
# Table 8.4: the cover's outside and the outside air, cHecOut1 + cHecOut2
# v^cHecOut3 per K and m² of cover, in a wind v (m/s).
OUTSIDE_STILL_W_M2K: Final = 2.8
OUTSIDE_PER_WIND: Final = 1.2
OUTSIDE_WIND_POWER: Final = 1.0
# Eq 8.21: each of the cover's two layers holds a tenth of its sheet's heat.
LAYER_SHARE: Final = 0.1
# Eq 8.44: water condensing on a surface, 6.4e-9 kg m⁻² s⁻¹ per W m⁻² K⁻¹
# of its convection and Pa of the vapour pressure above its saturation's,
# switched on by a sigmoid of slope 0.1 per Pa (Table 8.1, s_MV12 = -0.1).
CONDENSING_KG_PER_J_PA: Final = 6.4e-9
CONDENSING_SLOPE_PER_PA: Final = 0.1
# The state's entries: the air's temperature (°C), its water (g/kg), the
# water condensed on the cover since the stretch began (kg), then each
# glass's inside and outside layers (°C).
AIR: Final = 0
WATER: Final = 1
CONDENSED: Final = 2
FIRST_LAYER: Final = 3
LAYERS_A_GLASS: Final = 2
# How far a piece's linearised rates may stray from the equations' at its
# end, over the piece, before it is halved: in K for the temperatures, g/kg
# for the water, and kg for what condensed.
STRAYS_C: Final = 0.005
STRAYS_G_KG: Final = 0.001
STRAYS_KG: Final = 1e-3
# The shortest piece a stretch is halved to, s.
SHORTEST_PIECE_S: Final = 1e-3
# Each entry's step for the rates' tangents, by finite differences.
TANGENT_STEP: Final = 1e-6


@dataclass(frozen=True)
class Layers:
    """One glass's share of the cover: its area (m²), the conductance of its
    sheet through its thickness (λ / h, W m⁻² K⁻¹), the heat each of its two
    layers holds per m² and K (J), its sheet's longwave emissivity, and the
    share of the sun's shortwave it absorbs."""

    area_m2: float
    conductance_w_m2k: float
    layer_j_m2k: float
    emissivity: float
    absorptance: float

    @classmethod
    def of(cls, sheet: CoverMaterial, area_m2: float, sheet_m2k_w: float | None = None) -> Layers:
        """A sheet's layers over `area_m2`: as it conducts through its
        thickness, or with the resistance `sheet_m2k_w` it is given (a glass
        configured by its U, `climate.glazing.Glass`); each layer a tenth of
        its heat capacity; absorbing what it neither passes nor reflects."""
        resistance = (
            sheet.thickness_m / sheet.conductivity_w_m_k if sheet_m2k_w is None else sheet_m2k_w
        )
        return cls(
            area_m2=area_m2,
            conductance_w_m2k=1.0 / resistance,
            layer_j_m2k=LAYER_SHARE * sheet.thickness_m * sheet.volumetric_heat_capacity_j_m3_k,
            emissivity=sheet.longwave_emissivity,
            absorptance=1.0 - sheet.shortwave_beam_transmittance - sheet.shortwave_reflectance,
        )


@dataclass(frozen=True)
class Films:
    """How the cover's surfaces exchange heat with the air on each side: on
    the inside by Vanthoor's free convection, or by a constant coefficient
    if `inside_w_m2k` is given; on the outside by `still + per_wind v^power`
    per K and m², Vanthoor's unless others are given."""

    inside_w_m2k: float | None = None
    still_w_m2k: float = OUTSIDE_STILL_W_M2K
    per_wind: float = OUTSIDE_PER_WIND
    wind_power: float = OUTSIDE_WIND_POWER

    def inside(self, difference_c: float) -> float:
        """The inside film's coefficient across a difference of temperature,
        W m⁻² K⁻¹."""
        if self.inside_w_m2k is not None:
            return self.inside_w_m2k
        return float(FREE_CONVECTION * abs(difference_c) ** FREE_CONVECTION_POWER)

    def outside(self, wind_m_s: float) -> float:
        """The outside film's coefficient in a wind, W m⁻² K⁻¹."""
        return float(self.still_w_m2k + self.per_wind * wind_m_s**self.wind_power)


@dataclass(frozen=True)
class Held:
    """What holds through a stretch: the outside air's temperature (°C) and
    water (g/kg), the wind (m/s), the sky's temperature (°C), the heat given
    the air (W) by its equipment and the sun through the cover, the sun's
    shortwave on the house's floor outside (W), the air exchanged with the
    outside (m³/s), and the water the equipment takes (kg/s)."""

    outside_c: float
    outside_g_kg: float
    wind_m_s: float
    sky_c: float
    air_heat_w: float = 0.0
    sun_on_floor_w: float = 0.0
    exchanged_m3_s: float = 0.0
    drying_kg_s: float = 0.0


def vapour_pressure_pa(ratio_g_kg: float) -> float:
    """The water vapour's pressure in air holding `ratio_g_kg`."""
    return ratio_g_kg * ATMOSPHERE_PA / (WATER_PER_AIR_G_KG + ratio_g_kg)


def condensing_kg_m2_s(coefficient_w_m2k: float, vapour_pa: float, surface_c: float) -> float:
    """What condenses on a surface at `surface_c` from air of vapour
    pressure `vapour_pa`, through a film of `coefficient_w_m2k`, per m²
    (Vanthoor's eq 8.44): next to nothing below the surface's saturation."""
    above_pa = vapour_pa - float(saturation_pressure_pa(surface_c))
    # The sigmoid, written so that neither side overflows.
    if above_pa >= 0:
        switched = 1.0 / (1.0 + math.exp(-CONDENSING_SLOPE_PER_PA * above_pa))
    else:
        rising = math.exp(CONDENSING_SLOPE_PER_PA * above_pa)
        switched = rising / (1.0 + rising)
    return switched * CONDENSING_KG_PER_J_PA * coefficient_w_m2k * above_pa


class HouseNodes:
    """The house's air of `volume_m3` over a floor of `floor_m2`, beside its
    cover's `layers` (one for each glass it is of) and the sky, the cover's
    films as `films` gives them, water condensing on its inside unless
    `condenses` is False: see the module."""

    def __init__(
        self,
        volume_m3: float,
        floor_m2: float,
        layers: Sequence[Layers],
        films: Films | None = None,
        *,
        condenses: bool = True,
    ) -> None:
        self.volume_m3 = volume_m3
        self.condenses = condenses
        self.floor_m2 = floor_m2
        self.layers = tuple(layers)
        self.films = films or Films()
        self.size = FIRST_LAYER + LAYERS_A_GLASS * len(self.layers)
        cover_m2 = sum(layer.area_m2 for layer in self.layers)
        # Each glass's share of the floor the sky and the sun are taken
        # over, by its share of the cover.
        self._floor_shares = tuple(
            layer.area_m2 / cover_m2 if cover_m2 > 0 else 0.0 for layer in self.layers
        )
        self._air_j_k = AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K * volume_m3
        self._air_kg = AIR_DENSITY_KG_M3 * volume_m3
        strays = [STRAYS_C, STRAYS_G_KG, STRAYS_KG] + [STRAYS_C] * (LAYERS_A_GLASS * len(layers))
        self._strays = np.array(strays)

    def state(
        self, air_c: float, water_g_kg: float, layers_c: Sequence[tuple[float, float]]
    ) -> np.ndarray:
        """The state of air at `air_c` holding `water_g_kg`, beside its
        cover's layers at `layers_c`, each glass's inside and outside, none
        condensed yet."""
        if len(layers_c) != len(self.layers):
            raise ValueError(f"a cover of {len(self.layers)} glasses, not {len(layers_c)}")
        entries = [air_c, water_g_kg, 0.0]
        for inside, outside in layers_c:
            entries += [inside, outside]
        return np.array(entries)

    def layers_c(self, state: np.ndarray) -> tuple[tuple[float, float], ...]:
        """Each glass's inside and outside layers' temperatures in `state`."""
        return tuple(
            (
                float(state[FIRST_LAYER + LAYERS_A_GLASS * k]),
                float(state[FIRST_LAYER + LAYERS_A_GLASS * k + 1]),
            )
            for k in range(len(self.layers))
        )

    def fluxes(self, state: np.ndarray, held: Held) -> dict[str, float]:
        """Each flux at `state`, in W (heat) or kg/s (water), by its name,
        each glass's numbered from 0: what `rates` is made of."""
        air_c, water = float(state[AIR]), float(state[WATER])
        vapour_pa = vapour_pressure_pa(max(water, 0.0))
        sky_k4 = (held.sky_c + KELVIN) ** 4
        outside_film = self.films.outside(held.wind_m_s)
        found: dict[str, float] = {
            "air_outside_w": AIR_DENSITY_KG_M3
            * AIR_HEAT_CAPACITY_J_KG_K
            * held.exchanged_m3_s
            * (air_c - held.outside_c),
            "air_outside_kg_s": AIR_DENSITY_KG_M3
            * held.exchanged_m3_s
            * (water - held.outside_g_kg)
            / GRAMS_PER_KG,
        }
        for k, (layer, share) in enumerate(zip(self.layers, self._floor_shares, strict=True)):
            inside = float(state[FIRST_LAYER + LAYERS_A_GLASS * k])
            outside = float(state[FIRST_LAYER + LAYERS_A_GLASS * k + 1])
            film = self.films.inside(air_c - inside)
            found[f"air_cover_{k}_w"] = film * layer.area_m2 * (air_c - inside)
            found[f"condensing_{k}_kg_s"] = (
                layer.area_m2 * condensing_kg_m2_s(film, vapour_pa, inside)
                if self.condenses
                else 0.0
            )
            found[f"through_cover_{k}_w"] = (
                layer.conductance_w_m2k * layer.area_m2 * (inside - outside)
            )
            found[f"cover_outside_{k}_w"] = (
                outside_film * layer.area_m2 * (outside - held.outside_c)
            )
            found[f"cover_sky_{k}_w"] = (
                layer.emissivity
                * STEFAN_BOLTZMANN_W_M2K4
                * self.floor_m2
                * share
                * ((outside + KELVIN) ** 4 - sky_k4)
            )
            found[f"sun_cover_{k}_w"] = layer.absorptance * held.sun_on_floor_w * share
        return found

    def rates(self, state: np.ndarray, held: Held) -> np.ndarray:
        """How fast each entry of `state` moves, per second."""
        found = self.fluxes(state, held)
        rates = np.zeros(self.size)
        air_w = held.air_heat_w - found["air_outside_w"]
        water_kg_s = -held.drying_kg_s - found["air_outside_kg_s"]
        condensing_kg_s = 0.0
        for k, layer in enumerate(self.layers):
            condensed = found[f"condensing_{k}_kg_s"]
            air_w -= found[f"air_cover_{k}_w"]
            condensing_kg_s += condensed
            layer_j_k = layer.layer_j_m2k * layer.area_m2
            inside_w = (
                found[f"air_cover_{k}_w"]
                + LATENT_HEAT_J_KG * condensed
                - found[f"through_cover_{k}_w"]
            )
            outside_w = (
                found[f"through_cover_{k}_w"]
                + found[f"sun_cover_{k}_w"]
                - found[f"cover_outside_{k}_w"]
                - found[f"cover_sky_{k}_w"]
            )
            rates[FIRST_LAYER + LAYERS_A_GLASS * k] = inside_w / layer_j_k
            rates[FIRST_LAYER + LAYERS_A_GLASS * k + 1] = outside_w / layer_j_k
        rates[AIR] = air_w / self._air_j_k
        rates[WATER] = (water_kg_s - condensing_kg_s) * GRAMS_PER_KG / self._air_kg
        rates[CONDENSED] = condensing_kg_s
        return rates

    def linearised(self, state: np.ndarray, held: Held) -> tuple[np.ndarray, np.ndarray]:
        """The rates' tangent at `state`: the matrix J and the vector b of
        `rates(x) ≈ J x + b` about it, J by central differences."""
        jacobian = np.empty((self.size, self.size))
        for entry in range(self.size):
            step = TANGENT_STEP * max(1.0, abs(float(state[entry])))
            up, down = state.copy(), state.copy()
            up[entry] += step
            down[entry] -= step
            jacobian[:, entry] = (self.rates(up, held) - self.rates(down, held)) / (2 * step)
        return jacobian, self.rates(state, held) - jacobian @ state

    def course(self, state: np.ndarray, held: Held, horizon_s: float) -> NodesCourse:
        """How `state` goes through a stretch of up to `horizon_s` under
        `held`: see `NodesCourse`."""
        return NodesCourse(self, state, held, horizon_s)


@dataclass(frozen=True)
class _Piece:
    """A piece of a stretch, from `start_s` for `duration_s`: its state at
    its start, and its linearised equations, augmented, `[[J, b], [0, 0]]`."""

    start_s: float
    duration_s: float
    state: np.ndarray
    augmented: np.ndarray
    # Each step's exponential, by its length, for moments a step apart.
    _steps: dict[float, np.ndarray] = field(default_factory=dict, compare=False)

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s

    def moved(self, elapsed_s: float) -> np.ndarray:
        """Its state `elapsed_s` into it, augmented by a 1, exactly as its
        linear equations go."""
        moved: np.ndarray = matrix_exponential(self.augmented * elapsed_s) @ np.append(
            self.state, 1.0
        )
        return moved

    def at(self, elapsed_s: float) -> np.ndarray:
        """Its state `elapsed_s` into it."""
        return self.moved(elapsed_s)[:-1]

    def stepped(self, moved: np.ndarray, step_s: float) -> np.ndarray:
        """`moved`, a state of it augmented by a 1, `step_s` later."""
        if step_s not in self._steps:
            self._steps[step_s] = matrix_exponential(self.augmented * step_s)
        later: np.ndarray = self._steps[step_s] @ moved
        return later


class NodesCourse:
    """How a house's nodes go through a stretch, from `state`, under
    `held`: piece by piece, each linearised about its own start and solved
    exactly, each halved until its linearisation holds (see the module).
    Its pieces are worked out as far as asked, up to `horizon_s`."""

    def __init__(self, nodes: HouseNodes, state: np.ndarray, held: Held, horizon_s: float) -> None:
        self.nodes = nodes
        self.held = held
        self.horizon_s = horizon_s
        self.start = state
        self._pieces: list[_Piece] = []

    def _piece(self, start_s: float, state: np.ndarray) -> _Piece:
        """The piece from `state` at `start_s`, as long as its
        linearisation holds, up to the horizon."""
        jacobian, constant = self.nodes.linearised(state, self.held)
        size = self.nodes.size
        augmented = np.zeros((size + 1, size + 1))
        augmented[:size, :size] = jacobian
        augmented[:size, size] = constant
        duration = self.horizon_s - start_s
        while True:
            piece = _Piece(start_s, duration, state, augmented)
            if duration <= SHORTEST_PIECE_S:
                return piece
            end = piece.at(duration)
            strayed = np.abs(self.nodes.rates(end, self.held) - (jacobian @ end + constant))
            if np.all(strayed * duration / 2 <= self.nodes._strays):
                return piece
            duration /= 2

    def _covering(self, elapsed_s: float) -> _Piece:
        """The piece `elapsed_s` into the stretch lies in, worked out if it
        is not yet."""
        if not 0.0 <= elapsed_s <= self.horizon_s:
            raise ValueError(f"a stretch of {self.horizon_s:g} s, not {elapsed_s:g} s into it")
        if not self._pieces:
            self._pieces.append(self._piece(0.0, self.start))
        while self._pieces[-1].end_s < elapsed_s:
            last = self._pieces[-1]
            self._pieces.append(self._piece(last.end_s, last.at(last.duration_s)))
        return next(piece for piece in self._pieces if elapsed_s <= piece.end_s)

    def at(self, elapsed_s: float) -> np.ndarray:
        """The state `elapsed_s` into the stretch, from 0 to its horizon."""
        piece = self._covering(elapsed_s)
        return piece.at(elapsed_s - piece.start_s)

    def sampled(self, within_s: float, samples: int) -> list[np.ndarray]:
        """The state at `samples` moments evenly through `within_s`, the
        last at its end: a step's exponential taken once a piece."""
        step = within_s / samples
        states: list[np.ndarray] = []
        previous: tuple[_Piece, np.ndarray] | None = None
        for sample in range(1, samples + 1):
            piece = self._covering(within_s * sample / samples)
            if previous is not None and previous[0] is piece:
                moved = piece.stepped(previous[1], step)
            else:
                moved = piece.moved(within_s * sample / samples - piece.start_s)
            states.append(moved[:-1])
            previous = (piece, moved)
        return states

    def crossing_s(
        self,
        beyond: Callable[[np.ndarray], float],
        within_s: float,
        *,
        samples: int,
        edge_s: float,
        up: bool | None = None,
    ) -> float | None:
        """How long until `beyond`, a quantity of the state, first passes 0
        within `within_s`, found to `edge_s` by halving between `samples`
        moments; None if it does not. A 0 it starts at is passed at once if
        it moves the way `up` says, rising if True; otherwise from the side
        it moves to."""
        states = self.sampled(within_s, samples)
        start = beyond(self.start)
        if start == 0.0:
            first = beyond(states[0])
            if up is not None and first != 0.0 and (first > 0) == up:
                return 0.0
            start = first
        before = start > 0
        earlier = 0.0
        for sample, state in enumerate(states, start=1):
            later = within_s * sample / samples
            if (beyond(state) > 0) != before:
                while later - earlier > edge_s:
                    middle = (earlier + later) / 2
                    if (beyond(self.at(middle)) > 0) == before:
                        earlier = middle
                    else:
                        later = middle
                return later
            earlier = later
        return None
