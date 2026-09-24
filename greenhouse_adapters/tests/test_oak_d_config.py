import json
from typing import Any

import pytest
from greenhouse_protocol.enums import CaptureModality

from greenhouse_adapters.wur.common.oak_d import read_oak_d_config


def _stream(width: int, height: int, fx: float, ppx: float, ppy: float) -> dict[str, Any]:
    return {
        "height": height,
        "width": width,
        "ppx": ppx,
        "ppy": ppy,
        "fx": fx,
        "fy": fx,
        "coefs": [13.17, -143.7, -0.0009, 0.0016, 520.0, 12.9, -141.7, 512.6, 0, 0, 0, 0, 0, 0],
    }


def _config(**overrides: Any) -> str:
    """The shape of the 2024 canopy archive's configs/cam_1.json."""
    config: dict[str, Any] = {
        "name": "Oak-D S2 POE",
        "label": "oak-d-s2-poe",
        "setDefaultProfilePreset": "HIGH_ACCURACY",
        "lens_position": 113,
        "DeviceID": "19443010F1DD7F1300",
        "default_int": _stream(3840, 2160, 3115.85, 1866.7, 1109.56),
        "color_int": _stream(3840, 2160, 3115.85, 1866.7, 1109.56),
        "left_int": _stream(1280, 720, 810.46, 643.49, 398.1),
        "right_int": _stream(1280, 720, 811.3, 637.99, 363.62),
        "left_right_ext": {"info": "stereo", "data": [[1, 0, 0, 0.075]]},
        "left_rgb_ext": {"info": "left to rgb", "data": [[1, 0, 0, 0.0375]]},
    }
    config.update(overrides)
    return json.dumps(config)


def test_streams_map_to_modalities_and_depth_takes_the_colour_intrinsics() -> None:
    config = read_oak_d_config(_config())

    assert config.hardware_model == "Oak-D S2 POE"
    assert config.device_id == "19443010F1DD7F1300"
    assert set(config.intrinsics) == set(CaptureModality)
    colour = config.intrinsics[CaptureModality.RGB]
    assert (colour.width, colour.height, colour.fx, colour.ppx) == (3840, 2160, 3115.85, 1866.7)
    assert config.intrinsics[CaptureModality.DEPTH] == colour
    assert config.intrinsics[CaptureModality.INFRARED_RIGHT].fx == 811.3
    assert len(colour.distortion) == 14


def test_a_blank_device_id_is_unknown_not_empty() -> None:
    assert read_oak_d_config(_config(DeviceID="")).device_id is None


def test_a_config_missing_a_stream_is_refused() -> None:
    config = json.loads(_config())
    del config["right_int"]

    with pytest.raises(ValueError, match="right_int"):
        read_oak_d_config(json.dumps(config))
