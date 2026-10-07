"""What every airflow model does: produce the air over a grid."""

from typing import Protocol

from greenhouse_sim.fields.field import EnvironmentField, FieldGrid


class AirflowModel(Protocol):
    """Anything that can say what the air does over a grid at a moment."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        """The air over `grid` at `time_s`, as an environment field with, at
        least, its velocity."""
        ...
