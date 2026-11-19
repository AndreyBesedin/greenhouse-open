"""What a house is made of (P24.2, decision 0080): a cover's sheet, a
floor's surface and layers, and a screen's cloth, each named from the
catalogue below or given by its properties.

**A property** is a field in the unit its name states. Its schema gives its
unit and its range, with where each end of the range comes from
(`range_from`), as a crop model's parameters do (decision 0077). A material
given by its properties is refused outside the range, by field. A share of
radiation is a fraction of what falls on the material: what it passes and
what it reflects, of the shortwave, add up to all of it at most, and so do
what it emits (and so absorbs) and passes, of the longwave. A heat capacity
is per volume, the density times the specific heat, which is all that a
layer's conduction of heat needs of them.

**A named material** is the catalogue's: each of its values with its
source. A named material's values never change once published; a
correction is a new name. The catalogue names a material only when each of
its values has a source: the glass, the floor (named for the concrete its
values are), the soil and the thermal screen of Vanthoor's (2011) Dutch
Venlo house, as GreenLight 2.0.7 gives them. Other glasses, plastics and
cloths are given by their properties until a source gives each of their
values.

No model reads a material yet: the house air's models that do are to come
(P24.3 on).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, WrapValidator, model_validator

# Where each end of a range comes from.
NOTHING_BELOW: Final = "a share: nothing at least"
ALL_OF_IT: Final = "a share: all of what falls on it at most"
TYPES_OWN: Final = "none in its source: the field's type's"
# No material of a house holds more heat in a volume than water: its
# density times its specific heat, 1000 kg m⁻³ and 4180 J kg⁻¹ K⁻¹
# (Vanthoor 2011, Table 8.1).
MOST_HEAT_CAPACITY_J_M3_K: Final = 4.18e6
WATERS: Final = "water's, 1000 kg m⁻³ times 4180 J kg⁻¹ K⁻¹ (Vanthoor 2011, Table 8.1)"
# Where the catalogue's values come from.
VANTHOOR_NETHERLANDS: Final = "Vanthoor (2011), Table 8.2, the Netherlands"
GREENLIGHT: Final = "as GreenLight 2.0.7 gives it"


def _share(what: str) -> Any:
    return Field(
        ge=0.0,
        le=1.0,
        description=what,
        json_schema_extra={"unit": "-", "range_from": {"least": NOTHING_BELOW, "most": ALL_OF_IT}},
    )


def _positive(what: str, unit: str) -> Any:
    return Field(
        gt=0.0,
        description=what,
        json_schema_extra={"unit": unit, "range_from": {"least": TYPES_OWN, "most": TYPES_OWN}},
    )


def _heat_capacity() -> Any:
    return Field(
        gt=0.0,
        le=MOST_HEAT_CAPACITY_J_M3_K,
        description="its heat capacity per volume: its density times its specific heat",
        json_schema_extra={
            "unit": "J m⁻³ K⁻¹",
            "range_from": {"least": TYPES_OWN, "most": WATERS},
        },
    )


class _Material(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def _at_most_all(self, *shares: tuple[str, str]) -> None:
        """Refuse each pair of shares of one radiation that add up to more
        than all of it, naming both."""
        for first, second in shares:
            total = getattr(self, first) + getattr(self, second)
            if total > 1.0:
                raise ValueError(f"its {first} and {second} add up to {total:g}, above all of it")


# What the properties that more than one material has are.
REFLECTS: Final = "the share of the shortwave falling on it that it reflects"
EMITS: Final = "its longwave emissivity: the share of the longwave falling on it that it absorbs"
PASSES_LONGWAVE: Final = "the share of the longwave falling on it that it passes"
CONDUCTS: Final = "its thermal conductivity"
CONDUCTIVITY_UNIT: Final = "W m⁻¹ K⁻¹"


class CoverMaterial(_Material):
    """A sheet a cover is made of, given by its properties: what of the
    sun's beam, falling square to it, and of the sky's diffuse light it
    passes, what of the shortwave it reflects, what of the longwave it
    emits and passes, and the heat it conducts and holds."""

    shortwave_beam_transmittance: float = _share(
        "the share of the sun's beam, falling square to it, that it passes"
    )
    shortwave_diffuse_transmittance: float = _share(
        "the share of the sky's diffuse light falling on it that it passes"
    )
    shortwave_reflectance: float = _share(REFLECTS)
    longwave_emissivity: float = _share(EMITS)
    longwave_transmittance: float = _share(PASSES_LONGWAVE)
    thickness_m: float = _positive("its thickness", "m")
    conductivity_w_m_k: float = _positive(CONDUCTS, CONDUCTIVITY_UNIT)
    volumetric_heat_capacity_j_m3_k: float = _heat_capacity()

    @model_validator(mode="after")
    def _passes_and_reflects_at_most_all(self) -> Self:
        self._at_most_all(
            ("shortwave_beam_transmittance", "shortwave_reflectance"),
            ("shortwave_diffuse_transmittance", "shortwave_reflectance"),
            ("longwave_emissivity", "longwave_transmittance"),
        )
        return self


class ScreenCloth(_Material):
    """A cloth a screen is made of, given by its properties: what of the
    shortwave it passes and reflects, what of the longwave it emits and
    passes, the air it lets through when it is drawn, and the heat it holds.
    The air it lets through is Vanthoor's (2011) screen flux coefficient, K
    in f = K |ΔT|^(2/3): the air through each square metre of it, in m³ a
    second, for the difference of temperature across it."""

    shortwave_transmittance: float = _share(
        "the share of the shortwave falling on it that it passes"
    )
    shortwave_reflectance: float = _share(REFLECTS)
    longwave_emissivity: float = _share(EMITS)
    longwave_transmittance: float = _share(PASSES_LONGWAVE)
    air_permeability_m3_m2_s_k: float = Field(
        ge=0.0,
        description="its screen flux coefficient K, of f = K |ΔT|^(2/3) through it drawn",
        json_schema_extra={
            "unit": "m³ m⁻² s⁻¹ K^-2/3",
            "range_from": {"least": TYPES_OWN, "most": TYPES_OWN},
        },
    )
    thickness_m: float = _positive("its thickness", "m")
    volumetric_heat_capacity_j_m3_k: float = _heat_capacity()

    @model_validator(mode="after")
    def _passes_and_reflects_at_most_all(self) -> Self:
        self._at_most_all(
            ("shortwave_transmittance", "shortwave_reflectance"),
            ("longwave_emissivity", "longwave_transmittance"),
        )
        return self


class LayerMaterial(_Material):
    """What a layer of the floor, or of the soil under it, is made of, given
    by its properties: the heat it conducts and holds."""

    conductivity_w_m_k: float = _positive(CONDUCTS, CONDUCTIVITY_UNIT)
    volumetric_heat_capacity_j_m3_k: float = _heat_capacity()


class FloorSurface(_Material):
    """The floor's surface, given by its properties: what of the shortwave
    it reflects, and its longwave emissivity."""

    shortwave_reflectance: float = _share(REFLECTS)
    longwave_emissivity: float = _share(EMITS)


class CoverMaterialName(StrEnum):
    """A cover's sheet the catalogue names."""

    SINGLE_GLASS = "single_glass"


class LayerMaterialName(StrEnum):
    """A floor's or the soil's layer the catalogue names."""

    CONCRETE = "concrete"
    SOIL = "soil"


class ScreenClothName(StrEnum):
    """A screen's cloth the catalogue names."""

    THERMAL_SCREEN_CLOTH = "thermal_screen_cloth"


@dataclass(frozen=True)
class Catalogued[Properties: _Material]:
    """A named material: its properties, and where each value comes from,
    by its field."""

    properties: Properties
    sources: Mapping[str, str]


COVER_MATERIALS: Final[Mapping[CoverMaterialName, Catalogued[CoverMaterial]]] = {
    # 4 mm float glass on a Venlo house.
    CoverMaterialName.SINGLE_GLASS: Catalogued(
        CoverMaterial(
            shortwave_beam_transmittance=0.85,
            shortwave_diffuse_transmittance=0.773,
            shortwave_reflectance=0.13,
            longwave_emissivity=0.85,
            longwave_transmittance=0.0,
            thickness_m=0.004,
            conductivity_w_m_k=1.05,
            volumetric_heat_capacity_j_m3_k=2.184e6,
        ),
        {
            "shortwave_beam_transmittance": (
                f"{VANTHOOR_NETHERLANDS}: the roof's transmission of PAR and of NIR, 0.85 each,"
                " read square to the beam as the sunlight reads single glass (solar.glass)"
            ),
            "shortwave_diffuse_transmittance": (
                "derived: the beam's 0.85 times ASHRAE's incidence-angle modifier (b₀ = 0.1)"
                " averaged over the sky, as solar.glass derives it, 0.7727, rounded"
            ),
            "shortwave_reflectance": f"{VANTHOOR_NETHERLANDS}: of PAR and of NIR, 0.13 each",
            "longwave_emissivity": f"{VANTHOOR_NETHERLANDS}: the roof's FIR emission",
            "longwave_transmittance": f"{VANTHOOR_NETHERLANDS}: the roof's FIR transmission",
            "thickness_m": VANTHOOR_NETHERLANDS,
            "conductivity_w_m_k": VANTHOOR_NETHERLANDS,
            "volumetric_heat_capacity_j_m3_k": (
                f"{VANTHOOR_NETHERLANDS}: 2600 kg m⁻³ times 840 J kg⁻¹ K⁻¹"
            ),
        },
    ),
}

LAYER_MATERIALS: Final[Mapping[LayerMaterialName, Catalogued[LayerMaterial]]] = {
    LayerMaterialName.CONCRETE: Catalogued(
        LayerMaterial(conductivity_w_m_k=1.7, volumetric_heat_capacity_j_m3_k=2.024e6),
        {
            "conductivity_w_m_k": f"{VANTHOOR_NETHERLANDS}: the floor's",
            "volumetric_heat_capacity_j_m3_k": (
                f"{VANTHOOR_NETHERLANDS}: the floor's 2300 kg m⁻³ times 880 J kg⁻¹ K⁻¹"
            ),
        },
    ),
    LayerMaterialName.SOIL: Catalogued(
        LayerMaterial(conductivity_w_m_k=0.85, volumetric_heat_capacity_j_m3_k=1.73e6),
        {
            "conductivity_w_m_k": f"{VANTHOOR_NETHERLANDS}: the soil layers'",
            "volumetric_heat_capacity_j_m3_k": f"{VANTHOOR_NETHERLANDS}: the soil's",
        },
    ),
}

SCREEN_CLOTHS: Final[Mapping[ScreenClothName, Catalogued[ScreenCloth]]] = {
    ScreenClothName.THERMAL_SCREEN_CLOTH: Catalogued(
        ScreenCloth(
            shortwave_transmittance=0.6,
            shortwave_reflectance=0.35,
            longwave_emissivity=0.67,
            longwave_transmittance=0.15,
            thickness_m=0.35e-3,
            volumetric_heat_capacity_j_m3_k=3.6e5,
            air_permeability_m3_m2_s_k=0.05e-3,
        ),
        {
            "shortwave_transmittance": (
                f"{VANTHOOR_NETHERLANDS}: the thermal screen's of PAR and of NIR, 0.6 each"
            ),
            "shortwave_reflectance": (
                f"{VANTHOOR_NETHERLANDS}: the thermal screen's of PAR and of NIR, 0.35 each"
            ),
            "longwave_emissivity": f"{VANTHOOR_NETHERLANDS}: the thermal screen's FIR emission",
            "longwave_transmittance": (
                f"{VANTHOOR_NETHERLANDS}: the thermal screen's FIR transmission"
            ),
            "thickness_m": f"{VANTHOOR_NETHERLANDS}: the thermal screen's",
            "volumetric_heat_capacity_j_m3_k": (
                f"{VANTHOOR_NETHERLANDS}: the thermal screen's 200 kg m⁻³ times 1800 J kg⁻¹ K⁻¹"
            ),
            "air_permeability_m3_m2_s_k": (
                f"{VANTHOOR_NETHERLANDS}: the thermal screen's flux coefficient, {GREENLIGHT}"
            ),
        },
    ),
}


def _named_or_given[Properties: _Material](
    names: type[StrEnum], properties: type[Properties]
) -> WrapValidator:
    """A material read as the catalogue's, by its name, or as given by its
    properties: each refused for itself, so that a property refused is
    refused by its own field."""
    named, given = TypeAdapter(names), TypeAdapter(properties)

    def read(value: Any, _handler: Any) -> StrEnum | Properties:
        if isinstance(value, str):
            chosen: StrEnum = named.validate_python(value)
            return chosen
        return given.validate_python(value)

    return WrapValidator(read)


# A material as a component holds it: named from the catalogue, or given.
type CoverChoice = Annotated[
    CoverMaterialName | CoverMaterial, _named_or_given(CoverMaterialName, CoverMaterial)
]
type LayerChoice = Annotated[
    LayerMaterialName | LayerMaterial, _named_or_given(LayerMaterialName, LayerMaterial)
]
type ScreenChoice = Annotated[
    ScreenClothName | ScreenCloth, _named_or_given(ScreenClothName, ScreenCloth)
]


def material[Name: StrEnum, Properties: _Material](
    chosen: Name | Properties, catalogue: Mapping[Name, Catalogued[Properties]]
) -> Properties:
    """A material's properties: the catalogue's, if it is named, or those it
    is given."""
    if isinstance(chosen, StrEnum):
        return catalogue[chosen].properties
    return chosen
