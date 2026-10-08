"""The greenhouse's sensors, as more than one package names them."""

from enum import StrEnum


class SensorKind(StrEnum):
    """What a sensor is, and so what it reports."""

    # Point sensors, each reading one quantity of the air where it stands.
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    # An anemometer: the air's speed.
    AIR_SPEED = "air_speed"
    # Photosynthetically active radiation.
    PAR = "par"
    # A camera, seeing the scene from where it stands.
    CAMERA = "camera"
