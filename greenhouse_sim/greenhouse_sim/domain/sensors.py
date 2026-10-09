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
    # A weather station's instruments, outside the house, each reading one
    # quantity of the weather.
    OUTSIDE_TEMPERATURE = "outside_temperature"
    OUTSIDE_HUMIDITY = "outside_humidity"
    WIND_SPEED = "wind_speed"
    # A wind vane: the direction the wind blows from.
    WIND_DIRECTION = "wind_direction"
    BAROMETRIC_PRESSURE = "barometric_pressure"
    # A camera, seeing the scene from where it stands.
    CAMERA = "camera"
