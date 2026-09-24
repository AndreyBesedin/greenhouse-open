"""Oak-D S2 POE camera configuration files, as the WUR datasets ship them.

Each file gives pinhole intrinsics for the 4K colour stream (`color_int`) and
the two 720p mono streams (`left_int`, `right_int`), plus stereo extrinsics
between those streams. The depth images are aligned to the colour images
(dataset README), so the depth stream takes the colour intrinsics. The
extrinsics relate the camera's own streams to each other, not the camera to
the greenhouse, so they are not a pose and are not kept.

Profiled on 2026-09-14: the 2023 canopy camera's intrinsics equal 2024
`cam_19`'s exactly and the 2023 single-plant camera's equal 2024 `camir_27`'s,
so they are the same physical cameras; the 2023 files leave DeviceID blank."""

import json
from dataclasses import dataclass

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.sensor import CameraIntrinsics

_STREAMS: dict[str, tuple[CaptureModality, ...]] = {
    "color_int": (CaptureModality.RGB, CaptureModality.DEPTH),
    "left_int": (CaptureModality.INFRARED_LEFT,),
    "right_int": (CaptureModality.INFRARED_RIGHT,),
}
_INTRINSIC_FIELDS = ("width", "height", "fx", "fy", "ppx", "ppy")


@dataclass(frozen=True)
class OakDConfig:
    hardware_model: str
    device_id: str | None
    intrinsics: dict[CaptureModality, CameraIntrinsics]


def read_oak_d_config(raw: bytes | str) -> OakDConfig:
    config = json.loads(raw)
    missing = [key for key in _STREAMS if key not in config]
    if missing:
        raise ValueError(f"camera config is missing streams {missing}")

    intrinsics: dict[CaptureModality, CameraIntrinsics] = {}
    for key, modalities in _STREAMS.items():
        stream = config[key]
        absent = [name for name in _INTRINSIC_FIELDS if name not in stream]
        if absent:
            raise ValueError(f"camera config stream {key!r} is missing {absent}")
        value = CameraIntrinsics(
            width=stream["width"],
            height=stream["height"],
            fx=stream["fx"],
            fy=stream["fy"],
            ppx=stream["ppx"],
            ppy=stream["ppy"],
            distortion=tuple(float(c) for c in stream.get("coefs", ())),
        )
        for modality in modalities:
            intrinsics[modality] = value

    name = str(config.get("name") or "").strip()
    if not name:
        raise ValueError("camera config has no hardware name")
    device_id = str(config.get("DeviceID") or "").strip() or None
    return OakDConfig(hardware_model=name, device_id=device_id, intrinsics=intrinsics)
