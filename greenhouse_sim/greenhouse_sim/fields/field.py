"""A regular 3D field over the greenhouse's air, and how it is published.

A field covers a box, from its lowest corner `origin`, with a regular grid of
cells, `cells` of them along x, y and z, each `cell_size` wide. Each channel
holds one quantity of the air (`AirQuantity`) at every cell's centre: a
vector, such as the velocity, or a scalar, such as the temperature.

- **Sampling:** between centres, a field is sampled by trilinear
  interpolation. Beyond the outermost centres, out to the box's faces, it
  holds the nearest centres' values. Outside the box it says nothing.
- **Storage:** values run with x varying fastest, then y, then z, a vector's
  three components fastest of all. As a flat list, cell (i, j, k)'s value
  starts at (k × ny + j) × nx + i, times three for a vector. In memory, a
  channel is an array of shape (nz, ny, nx), or (nz, ny, nx, 3) for a
  vector.
- **Publishing:** a field is published as a `FieldDocument`, each channel's
  values as little-endian 32-bit floats in base64, with their range for a
  legend.
"""

import base64
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Final, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from greenhouse_sim.domain.air import AIR_UNITS, VECTOR_QUANTITIES, AirQuantity
from greenhouse_sim.world.geometry import Vector3

# The version of the published field format; a viewer refuses any other.
FIELD_SCHEMA_VERSION: Final = 1
VECTOR_COMPONENTS: Final = 3
# How a channel's values are written: little-endian 32-bit floats, base64.
ENCODING: Final = "float32-le-base64"
_FLOAT32_LE: Final = np.dtype("<f4")
# A box a whole number of cells long, give or take rounding, takes that many.
_CELL_ROUNDING: Final = 1e-9

type PositiveSize = Annotated[float, Field(gt=0)]


class CellCounts(BaseModel):
    """How many cells a grid has along x, y and z."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: PositiveInt
    y: PositiveInt
    z: PositiveInt


class FieldGrid(BaseModel):
    """A box divided into a regular grid of cells."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The box's lowest corner, in metres in the greenhouse's frame.
    origin: Vector3
    # Each cell's size along x, y and z, in metres.
    cell_size: Vector3
    cells: CellCounts

    @model_validator(mode="after")
    def _cells_have_a_size(self) -> FieldGrid:
        if min(self.cell_size.x, self.cell_size.y, self.cell_size.z) <= 0:
            raise ValueError("a cell's size must be positive along x, y and z")
        return self

    @classmethod
    def over(cls, minimum: Vector3, maximum: Vector3, cell_m: float) -> FieldGrid:
        """The grid over the box from `minimum` to `maximum`, with as many
        cells along each axis as make them at most `cell_m` wide."""
        extent = (maximum.x - minimum.x, maximum.y - minimum.y, maximum.z - minimum.z)
        counts = tuple(max(1, math.ceil(length / cell_m - _CELL_ROUNDING)) for length in extent)
        nx, ny, nz = counts
        return cls(
            origin=minimum,
            cell_size=Vector3(x=extent[0] / nx, y=extent[1] / ny, z=extent[2] / nz),
            cells=CellCounts(x=nx, y=ny, z=nz),
        )

    @property
    def shape(self) -> tuple[int, int, int]:
        """How many cells along x, y and z."""
        return self.cells.x, self.cells.y, self.cells.z

    @property
    def maximum(self) -> Vector3:
        """The box's highest corner."""
        nx, ny, nz = self.shape
        return Vector3(
            x=self.origin.x + nx * self.cell_size.x,
            y=self.origin.y + ny * self.cell_size.y,
            z=self.origin.z + nz * self.cell_size.z,
        )

    def centres(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The cells' centres along x, y and z."""
        nx, ny, nz = self.shape
        return (
            self.origin.x + (np.arange(nx) + 1 / 2) * self.cell_size.x,
            self.origin.y + (np.arange(ny) + 1 / 2) * self.cell_size.y,
            self.origin.z + (np.arange(nz) + 1 / 2) * self.cell_size.z,
        )

    def contains(self, point: Vector3) -> bool:
        top = self.maximum
        return (
            self.origin.x <= point.x <= top.x
            and self.origin.y <= point.y <= top.y
            and self.origin.z <= point.z <= top.z
        )


def _corners(coordinate: float, origin: float, size: float, count: int) -> tuple[int, int, float]:
    """The two neighbouring centres a coordinate lies between along one axis,
    and how far it lies from the first to the second, from 0 to 1."""
    position = min(max((coordinate - origin) / size - 1 / 2, 0.0), count - 1)
    low = min(int(position), max(count - 2, 0))
    return low, min(low + 1, count - 1), position - low


@dataclass(frozen=True, eq=False)
class EnvironmentField:
    """The air over a grid at one moment, channel by channel."""

    field_id: str
    # What computed it, such as `synthetic:shear` or `openfoam:…`.
    source: str
    grid: FieldGrid
    # The simulated time it describes, in seconds.
    time_s: float
    channels: Mapping[AirQuantity, np.ndarray]

    def __post_init__(self) -> None:
        nx, ny, nz = self.grid.shape
        for quantity, values in self.channels.items():
            expected: tuple[int, ...] = (nz, ny, nx)
            if quantity in VECTOR_QUANTITIES:
                expected += (VECTOR_COMPONENTS,)
            if values.shape != expected:
                raise ValueError(f"{quantity} has shape {values.shape}, not {expected}")
            if not np.isfinite(values).all():
                raise ValueError(f"{quantity} has values that are not finite")

    def sample(self, quantity: AirQuantity, point: Vector3) -> Vector3 | float | None:
        """The quantity at a point: interpolated between the cells' centres,
        or None outside the field's box or for a quantity it lacks."""
        values = self.channels.get(quantity)
        if values is None or not self.grid.contains(point):
            return None
        grid = self.grid
        nx, ny, nz = grid.shape
        i0, i1, fx = _corners(point.x, grid.origin.x, grid.cell_size.x, nx)
        j0, j1, fy = _corners(point.y, grid.origin.y, grid.cell_size.y, ny)
        k0, k1, fz = _corners(point.z, grid.origin.z, grid.cell_size.z, nz)
        mixed = (
            values[k0, j0, i0] * (1 - fx) * (1 - fy) * (1 - fz)
            + values[k0, j0, i1] * fx * (1 - fy) * (1 - fz)
            + values[k0, j1, i0] * (1 - fx) * fy * (1 - fz)
            + values[k0, j1, i1] * fx * fy * (1 - fz)
            + values[k1, j0, i0] * (1 - fx) * (1 - fy) * fz
            + values[k1, j0, i1] * fx * (1 - fy) * fz
            + values[k1, j1, i0] * (1 - fx) * fy * fz
            + values[k1, j1, i1] * fx * fy * fz
        )
        if quantity in VECTOR_QUANTITIES:
            return Vector3(x=float(mixed[0]), y=float(mixed[1]), z=float(mixed[2]))
        return float(mixed)

    def document(self) -> FieldDocument:
        """The field as it is published."""
        return FieldDocument(
            field_id=self.field_id,
            source=self.source,
            time_s=self.time_s,
            grid=self.grid,
            channels=[_channel_document(q, v) for q, v in self.channels.items()],
        )

    @classmethod
    def from_document(cls, document: FieldDocument) -> EnvironmentField:
        nx, ny, nz = document.grid.shape
        channels = {}
        for channel in document.channels:
            flat = np.frombuffer(base64.b64decode(channel.data), dtype=_FLOAT32_LE)
            shape: tuple[int, ...] = (nz, ny, nx)
            if channel.components == VECTOR_COMPONENTS:
                shape += (VECTOR_COMPONENTS,)
            channels[channel.quantity] = flat.astype(np.float64).reshape(shape)
        return cls(
            field_id=document.field_id,
            source=document.source,
            grid=document.grid,
            time_s=document.time_s,
            channels=channels,
        )


class ChannelDocument(BaseModel):
    """One channel of a published field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quantity: AirQuantity
    unit: str
    # 3 for a vector, 1 for a scalar.
    components: Literal[1, 3]
    encoding: Literal["float32-le-base64"] = ENCODING
    # Its values, in the field's order and encoding.
    data: str
    # The least and greatest value, or magnitude for a vector, for a legend.
    minimum: float
    maximum: float


class FieldDocument(BaseModel):
    """An environment field as it is published to a viewer: its grid, and
    each channel's values over it (see the module's description)."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_serialization_defaults_required=True
    )

    schema_version: Literal[1] = FIELD_SCHEMA_VERSION
    field_id: str
    source: str
    time_s: float
    grid: FieldGrid
    channels: list[ChannelDocument]


def _channel_document(quantity: AirQuantity, values: np.ndarray) -> ChannelDocument:
    vector = quantity in VECTOR_QUANTITIES
    sizes = np.linalg.norm(values, axis=-1) if vector else values
    return ChannelDocument(
        quantity=quantity,
        unit=AIR_UNITS[quantity],
        components=VECTOR_COMPONENTS if vector else 1,
        data=base64.b64encode(values.astype(_FLOAT32_LE).tobytes()).decode("ascii"),
        minimum=float(sizes.min()),
        maximum=float(sizes.max()),
    )


def field_json_schema() -> dict[str, object]:
    """The JSON Schema a viewer validates published fields against, written
    as `field.schema.json` next to this module."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **FieldDocument.model_json_schema(mode="serialization"),
    }
