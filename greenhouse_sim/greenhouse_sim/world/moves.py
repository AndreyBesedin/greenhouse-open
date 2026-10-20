"""Equipment and sensors moved across the floor (#209): a person places a
heater, a fan or a sensor elsewhere in the house, and the run uses it there.

A move is a displacement along the ground, in the world's axes, of a piece of
equipment or a sensor from where its layout places it: as the viewer sees it
dragged, whichever way the greenhouse is turned in the world. It is turned
into the greenhouse's own frame and added to the item's place, its height
kept: a unit's base, a fan's centre, a sensor's position; a camera's target
moves with it, so that it looks the same way. Moves are data, as commands
are: the same moves always place the same items, and a run's layout with
them is another layout, and another run.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from greenhouse_sim.world.equipment import Fan
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.sensors import Camera


@dataclass(frozen=True)
class Move:
    """Move the equipment or sensor `item_id` by `dx_m` and `dy_m` along the
    world's x and y axes."""

    item_id: str
    dx_m: float
    dy_m: float


def _inverse(rotation: Quaternion) -> Quaternion:
    return Quaternion(w=rotation.w, x=-rotation.x, y=-rotation.y, z=-rotation.z)


def _level(vector: Vector3) -> Vector3:
    return Vector3(x=vector.x, y=vector.y, z=0.0)


def _moved(point: Vector3, by: Vector3) -> Vector3:
    return Vector3(x=point.x + by.x, y=point.y + by.y, z=point.z)


def moved(layout: Layout, origin: Transform, moves: Sequence[Move]) -> Layout:
    """`layout` with its items moved, its greenhouse placed in the world by
    `origin`. A move of an item it does not have, or a second move of one,
    is refused: a ValueError that names it."""
    equipment_ids = {piece.actuator_id for piece in layout.equipment}
    sensor_ids = {sensor.sensor_id for sensor in layout.sensors}
    unknown = sorted({m.item_id for m in moves} - equipment_ids - sensor_ids)
    if unknown:
        raise ValueError(f"no equipment or sensor to move: {', '.join(unknown)}")
    seen: set[str] = set()
    for move in moves:
        if move.item_id in seen:
            raise ValueError(f"{move.item_id} is moved twice")
        seen.add(move.item_id)
    # Each displacement in the greenhouse's own frame, level.
    turn = _inverse(origin.rotation)
    by = {m.item_id: _level(turn.rotate(Vector3(x=m.dx_m, y=m.dy_m, z=0.0))) for m in moves}
    equipment = [
        piece
        if piece.actuator_id not in by
        else piece.model_copy(update={"position": _moved(piece.position, by[piece.actuator_id])})
        if isinstance(piece, Fan)
        else piece.model_copy(update={"base": _moved(piece.base, by[piece.actuator_id])})
        for piece in layout.equipment
    ]
    sensors = [
        sensor
        if sensor.sensor_id not in by
        else sensor.model_copy(
            update={
                "position": _moved(sensor.position, by[sensor.sensor_id]),
                "target": _moved(sensor.target, by[sensor.sensor_id]),
            }
        )
        if isinstance(sensor, Camera)
        else sensor.model_copy(update={"position": _moved(sensor.position, by[sensor.sensor_id])})
        for sensor in layout.sensors
    ]
    return layout.model_copy(update={"equipment": equipment, "sensors": sensors})
