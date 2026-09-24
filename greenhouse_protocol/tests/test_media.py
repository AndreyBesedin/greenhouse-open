from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import CaptureModality, SourceType
from greenhouse_protocol.media import MediaCapture
from greenhouse_protocol.provenance import RecordSource


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
