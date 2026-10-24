"""What a device does to the air: its capabilities (P14.5, decision 0054).

A device is known by what it can do and by its shape, not by its kind. What
it can do is a few capabilities, each with the parameters it takes, all at
full level: a device at a level does that share of each
(`greenhouse_sim.climate.sources`).

- **It moves air** (`MovesAir`): it blows its flow as a round jet from its
  outlet, along its axis, as a fan does.
- **It heats** (`Heats`): its power is the house's heating, which a heating
  loop runs and the heat log meters. Blown from an outlet, as a unit
  heater's warm air is, or else given to the air around its body.
- **It dries** (`Dries`): it takes water out of the air around its body,
  as a dehumidifier does; a dehumidifying loop runs it.

Besides its work, a device may give off heat (`WasteHeat`), to the air
around its body: no loop runs it for that heat, and it is not heating.

A device has one level, which scales all of them at once: an action names
the device, not one of its capabilities, until a device's capabilities run
apart.
"""

from dataclasses import dataclass
from typing import Protocol

from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import Vector3


@dataclass(frozen=True)
class Outlet:
    """Where a device blows from: its outlet's centre, in the greenhouse's
    frame, the unit vector it blows along, and the outlet's diameter."""

    centre: Vector3
    axis: Vector3
    diameter_m: float


@dataclass(frozen=True)
class MovesAir:
    """It blows `flow_m3_s` of air at full level, as a round jet from its
    `outlet` (`greenhouse_sim.climate.jets`)."""

    outlet: Outlet
    flow_m3_s: float


@dataclass(frozen=True)
class Heats:
    """It heats the air by `power_w` at full level: blown from its `outlet`,
    if it has one, or else given to the air around its body."""

    power_w: float
    outlet: Outlet | None = None


@dataclass(frozen=True)
class Dries:
    """It takes `removal_kg_h` of water out of the air around its body at
    full level."""

    removal_kg_h: float


@dataclass(frozen=True)
class WasteHeat:
    """The heat, `heat_w` at full level, it gives the air around its body as
    it works: not heating."""

    heat_w: float


# What a device does to the air.
type Capability = MovesAir | Heats | Dries | WasteHeat


class Device(Protocol):
    """A device as the climate knows it: by its identifier, its body (its
    `fixture`, around which it gives what it does not blow) and what it
    can do."""

    @property
    def actuator_id(self) -> str: ...

    def fixture(self) -> Fixture:
        """Its body, placed in the greenhouse."""
        ...

    def capabilities(self) -> tuple[Capability, ...]:
        """What it does to the air, at full level."""
        ...
