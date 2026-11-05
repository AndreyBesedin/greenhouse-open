"""The demo's video as the README plays it, cut from what Playwright records.

Playwright records the walk-through (`greenhouse_sim/web/e2e/readme-demo.spec.ts`)
from the moment its page opens, blank until the house is drawn, and GitHub
shows a README's video by its first frame until it plays. The walk-through
writes, beside its recording, when its opening shot is ready; the cut
starts there, plays at twice the speed, and is an MP4 that GitHub plays,
within the size it takes for an uploaded video and the minute a README's
video is kept to.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# The file the walk-through writes beside its recording, and its field.
OPENING_MARK = "opening.json"
OPENING_FIELD = "opening_s"
# How long after the walk-through's mark the cut starts: the video started
# a moment before the test's clock did. The walk-through lingers on its first
# caption from the mark on, for DEMO_PAUSE_MS, as `npm run demo:record` sets it.
OPENING_MARGIN_S = 1.0
SPEED = 2
FRAMES_PER_S = 25
# GitHub takes a video uploaded to an issue or a pull request up to 10 MB.
UPLOAD_LIMIT_BYTES = 10_000_000
# A README's video shows the main features, in under a minute.
LONGEST_S = 60.0
# H.264 in an MP4, which every browser plays, its index first so that the
# first frame shows before the whole file has arrived.
ENCODING = (
    "-an",
    "-c:v",
    "libx264",
    "-preset",
    "slow",
    "-crf",
    "28",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
)


class Uncut(RuntimeError):
    """The recording cannot be cut; the message says why."""


def opening_s(recording: Path) -> float:
    """When the opening shot is ready, in seconds into `recording`, as the
    walk-through wrote it beside the video."""
    mark = recording.parent / OPENING_MARK
    if not mark.is_file():
        raise Uncut(f"No {OPENING_MARK} beside {recording}: was it recorded by a walk-through?")
    return float(json.loads(mark.read_text())[OPENING_FIELD])


def cut_command(ffmpeg: str, recording: Path, start_s: float, video: Path) -> list[str]:
    """ffmpeg's command for the cut: from `start_s` on, sped up, re-timed to
    a steady frame rate."""
    frames = f"trim=start={start_s:.3f},setpts=(PTS-STARTPTS)/{SPEED},fps={FRAMES_PER_S}"
    reads = [ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(recording)]
    return [*reads, "-vf", frames, *ENCODING, str(video)]


def first_frame_command(ffmpeg: str, video: Path, image: Path) -> list[str]:
    return [ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(video), "-frames:v", "1", str(image)]


def duration_s(ffmpeg: str, video: Path) -> float:
    """How long `video` lasts, by the ffprobe that comes with `ffmpeg`."""
    ffprobe = str(Path(ffmpeg).with_name("ffprobe"))
    asked = ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]
    return float(subprocess.run([ffprobe, *asked], check=True, capture_output=True).stdout)


def cut(ffmpeg: str, recording: Path, version: str) -> tuple[Path, Path]:
    """Cuts `recording` into `greenhouse-open-<version>.mp4` beside it, and
    draws its first frame, the README's preview, as a PNG beside that."""
    video = recording.parent / f"greenhouse-open-{version}.mp4"
    image = video.with_name(f"{video.stem}-first-frame.png")
    start_s = opening_s(recording) + OPENING_MARGIN_S
    subprocess.run(cut_command(ffmpeg, recording, start_s, video), check=True)
    subprocess.run(first_frame_command(ffmpeg, video, image), check=True)
    size = video.stat().st_size
    if size > UPLOAD_LIMIT_BYTES:
        raise Uncut(
            f"{video} is {size / 1e6:.1f} MB, more than GitHub takes for an uploaded video "
            f"({UPLOAD_LIMIT_BYTES / 1e6:.0f} MB)."
        )
    lasts_s = duration_s(ffmpeg, video)
    if lasts_s > LONGEST_S:
        raise Uncut(
            f"{video} lasts {lasts_s:.1f} s, longer than a README's video may "
            f"({LONGEST_S:.0f} s): shorten the walk-through, or its DEMO_PAUSE_MS."
        )
    return video, image
