from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import CaptureModality, SourceType
from greenhouse_protocol.media import CameraFrame, CameraPose, MediaCapture
from greenhouse_protocol.provenance import RecordSource
from greenhouse_protocol.sensor import CameraIntrinsics


def _capture(**overrides: object) -> MediaCapture:
    defaults: dict[str, object] = dict(
        capture_id="wur24_cam_1_20241002T100614Z_rgb",
        greenhouse_id="wur_agc4_2024",
        compartment_id="3.06",
        sensor_id="wur24_cam_1",
        timestamp=datetime(2024, 10, 2, 10, 6, 14, tzinfo=UTC),
        modality=CaptureModality.RGB,
        artifact_uri=(
            "wur_agc4-challenge-2024/autonomous_greenhouse_challenge4_canopy_camera.zip"
            "!dataset4tu/cam_1/cam_1_2024_10_02_12_06_14_rgb.png"
        ),
        source=RecordSource(type=SourceType.IMPORTED_DATA, source_id="wur_agc4-challenge-2024"),
    )
    defaults.update(overrides)
    return MediaCapture(**defaults)


def test_a_capture_references_its_artifact_without_holding_pixels() -> None:
    capture = _capture()

    assert capture.modality == CaptureModality.RGB
    assert capture.artifact_uri.endswith("_rgb.png")
    assert set(MediaCapture.model_fields) == {
        "capture_id",
        "greenhouse_id",
        "compartment_id",
        "sensor_id",
        "timestamp",
        "modality",
        "artifact_uri",
        "source",
    }


def test_a_capture_is_immutable() -> None:
    capture = _capture()

    with pytest.raises(ValidationError):
        capture.sensor_id = "another"  # type: ignore[misc]


def test_a_capture_without_a_timezone_is_refused() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _capture(timestamp=datetime(2024, 10, 2, 12, 6, 14))


def test_capture_modalities_match_what_the_canopy_cameras_write() -> None:
    assert {member.value for member in CaptureModality} == {
        "RGB",
        "DEPTH",
        "INFRARED_LEFT",
        "INFRARED_RIGHT",
    }


LEVEL = CameraPose(x_m=0.6, y_m=3.2, z_m=2.2, qw=1.0, qx=0.0, qy=0.0, qz=0.0)
INTRINSICS = CameraIntrinsics(width=640, height=480, fx=457.0, fy=457.0, ppx=320, ppy=240)


def test_a_pose_turns_by_a_unit_quaternion() -> None:
    half_turn = CameraPose(x_m=0, y_m=0, z_m=1, qw=0.0, qx=0.0, qy=0.0, qz=1.0)

    assert half_turn.qz == 1.0
    with pytest.raises(ValidationError, match="unit quaternion"):
        CameraPose(x_m=0, y_m=0, z_m=1, qw=1.0, qx=0.0, qy=0.0, qz=1.0)


def test_a_frame_holds_a_pose_intrinsics_and_its_modalities_not_pixels() -> None:
    frame = CameraFrame(
        frame_id="sim_front_camera_20260101T001000Z_frame",
        greenhouse_id="climate_box",
        sensor_id="front_camera",
        timestamp=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
        pose=LEVEL,
        intrinsics=INTRINSICS,
        modalities=(CaptureModality.RGB, CaptureModality.DEPTH),
        source=RecordSource(type=SourceType.SIMULATION, source_id="climate_box-climate-run"),
    )

    assert frame.capture_ids == ()
    assert frame.delivered_at is None
    assert CameraFrame.model_validate_json(frame.model_dump_json()) == frame


def test_a_frame_holds_something() -> None:
    with pytest.raises(ValidationError):
        CameraFrame(
            frame_id="empty",
            greenhouse_id="climate_box",
            sensor_id="front_camera",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            pose=LEVEL,
            intrinsics=INTRINSICS,
            modalities=(),
            source=RecordSource(type=SourceType.SIMULATION, source_id="run"),
        )
