"""The demo's video, cut from Playwright's recording where the walk-through
marks its opening shot (`greenhouse_dev.demo_video`), so that its first
frame, the README's preview, is the house rather than the blank page
before it."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from greenhouse_dev import demo_video

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not on the path"
)
BLANK_S = 2.0
SHOWN_S = 2.0


def mark(recording: Path, opening_s: float) -> None:
    (recording.parent / demo_video.OPENING_MARK).write_text(
        json.dumps({demo_video.OPENING_FIELD: opening_s})
    )


def test_the_cut_starts_after_the_opening_mark_sped_up() -> None:
    command = demo_video.cut_command("ffmpeg", Path("in.webm"), 14.2, Path("out.mp4"))

    frames = command[command.index("-vf") + 1]
    assert frames == f"trim=start=14.200,setpts=(PTS-STARTPTS)/2,fps={demo_video.FRAMES_PER_S}"
    assert command[-1] == "out.mp4"
    assert {"libx264", "yuv420p", "+faststart"} <= set(command)


def test_a_recording_without_its_mark_is_not_cut(tmp_path: Path) -> None:
    with pytest.raises(demo_video.Uncut, match=f"No {demo_video.OPENING_MARK} beside"):
        demo_video.opening_s(tmp_path / "video.webm")


def recorded(folder: Path) -> Path:
    """A recording as Playwright makes one: blank, then the house, here
    black, then white."""
    recording = folder / "video.webm"
    sources = [
        arg
        for colour, seconds in (("black", BLANK_S), ("white", SHOWN_S))
        for arg in ("-f", "lavfi", "-i", f"color=c={colour}:s=64x48:r=25:d={seconds}")
    ]
    joined = ["-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-c:v", "ffv1", "-f", "matroska"]
    subprocess.run([FFMPEG, "-v", "error", *sources, *joined, str(recording)], check=True)
    return recording


def brightness(image: Path) -> int:
    """The image's mean grey level, 0 to 255."""
    grey = [FFMPEG, "-v", "error", "-i", str(image), "-vf", "scale=1:1,format=gray"]
    return subprocess.run([*grey, "-f", "rawvideo", "-"], check=True, capture_output=True).stdout[0]


def seconds(video: Path) -> float:
    probe = shutil.which("ffprobe") or "ffprobe"
    shown = ["-show_entries", "format=duration", "-of", "csv=p=0", str(video)]
    return float(subprocess.run([probe, "-v", "error", *shown], capture_output=True).stdout)


@needs_ffmpeg
def test_the_videos_first_frame_is_the_opening_shot(tmp_path: Path) -> None:
    recording = recorded(tmp_path)
    # The page ready a moment before the house is drawn: the margin takes
    # the cut past the blank.
    mark(recording, BLANK_S - demo_video.OPENING_MARGIN_S / 2)

    video, first_frame = demo_video.cut(FFMPEG, recording, "9.9.9")

    assert video == tmp_path / "greenhouse-open-9.9.9.mp4"
    assert brightness(first_frame) > 200
    left_s = BLANK_S + SHOWN_S - (BLANK_S + demo_video.OPENING_MARGIN_S / 2)
    assert seconds(video) == pytest.approx(left_s / demo_video.SPEED, abs=0.1)


@needs_ffmpeg
def test_a_mark_before_the_house_is_drawn_leaves_the_blank_in(tmp_path: Path) -> None:
    # The mark, not a guess, says where the cut starts: one set too early
    # shows the blank page first, as every recording did before the mark.
    recording = recorded(tmp_path)
    mark(recording, 0.0)

    _, first_frame = demo_video.cut(FFMPEG, recording, "9.9.9")

    assert brightness(first_frame) < 50


@needs_ffmpeg
def test_a_video_too_large_to_upload_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = recorded(tmp_path)
    mark(recording, 0.0)
    monkeypatch.setattr(demo_video, "UPLOAD_LIMIT_BYTES", 10)

    with pytest.raises(demo_video.Uncut, match="more than GitHub takes"):
        demo_video.cut(FFMPEG, recording, "9.9.9")
