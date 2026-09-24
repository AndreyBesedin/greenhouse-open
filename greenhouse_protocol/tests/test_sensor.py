import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import CaptureModality, SourceType
from greenhouse_protocol.provenance import RecordSource
from greenhouse_protocol.sensor import CameraIntrinsics, Sensor

COLOUR = CameraIntrinsics(
    width=3840, height=2160, fx=3115.85, fy=3115.85, ppx=1866.7, ppy=1109.56, distortion=(0.1,)
)


def test_a_sensor_keeps_intrinsics_per_stream_and_no_pose() -> None:
    sensor = Sensor(
        sensor_id="wur24_cam_1",
        greenhouse_id="wur_agc4_2024",
        compartment_id="3.06",
        hardware_model="Oak-D S2 POE",
        device_id="19443010F1DD7F1300",
        intrinsics={CaptureModality.RGB: COLOUR, CaptureModality.DEPTH: COLOUR},
        nominal_mounting="About 1.5 m above the growing crop, facing downwards.",
        source=RecordSource(type=SourceType.IMPORTED_DATA, source_id="wur_agc4-challenge-2024"),
    )

    assert sensor.intrinsics[CaptureModality.DEPTH] == COLOUR
    assert not any("pose" in field for field in Sensor.model_fields)


def test_a_sensor_without_optics_or_a_serial_is_valid() -> None:
    sensor = Sensor(
        sensor_id="probe",
        greenhouse_id="gh",
        hardware_model="substrate probe",
        source=RecordSource(type=SourceType.IMPORTED_DATA),
    )

    assert (sensor.intrinsics, sensor.device_id, sensor.compartment_id) == ({}, None, None)


@pytest.mark.parametrize("field", ["width", "height", "fx", "fy"])
def test_intrinsics_refuse_non_positive_sizes_and_focal_lengths(field: str) -> None:
    values = COLOUR.model_dump() | {field: 0}

    with pytest.raises(ValidationError):
        CameraIntrinsics(**values)
