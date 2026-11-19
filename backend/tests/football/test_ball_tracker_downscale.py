from __future__ import annotations

import time
from pathlib import Path

import cv2

from app.football.pipeline.ball_tracker import (
    BallTrack,
    ClassicalMOG2HoughDetector,
    track_ball_in_video,
)
from app.football.pipeline.touch_events import detect_video_touch_events
from tests.football.synthetic import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)

TOUCH_TIMES_MS = [900, 1700, 2500, 3300, 4100]


def _spec_for_resolution(width: int, height: int) -> SyntheticJugglingSpec:
    """Same ball motion in every resolution: all pixel quantities scale with frame width."""
    k = width / 640.0
    return SyntheticJugglingSpec(
        duration_s=(TOUCH_TIMES_MS[-1] + 1000) / 1000.0,
        fps=30,
        width=width,
        height=height,
        ball_radius_px=round(24 * k),
        touch_times_ms=list(TOUCH_TIMES_MS),
        touch_y_px=280.0 * k,
        ground_y_px=340.0 * k,
        peak_height_diameters=2.1,
        background_noise_std=2.0,
        seed=909,
    )


def _clip_path(tmp_path: Path, width: int, height: int, name: str) -> Path:
    return generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=_spec_for_resolution(width, height),
        clip_name=name,
        include_audio=False,
    ).video_path


def _track(tmp_path: Path, width: int, height: int, name: str) -> tuple[BallTrack, float]:
    video_path = _clip_path(tmp_path, width, height, name)
    start = time.perf_counter()
    track = track_ball_in_video(video_path)
    return track, time.perf_counter() - start


def test_downscaled_tracking_is_consistent_with_low_resolution(
    tmp_path: Path,
) -> None:
    high, _ = _track(tmp_path, 1280, 720, "high_1280x720")
    low, _ = _track(tmp_path, 320, 180, "low_320x180")

    # Metadata and coordinates stay in the ORIGINAL video resolution.
    assert (high.frame_width, high.frame_height) == (1280, 720)
    assert (low.frame_width, low.frame_height) == (320, 180)
    assert 40.0 <= high.median_radius_px <= 56.0  # true radius is 48 px
    assert max(pt.x for pt in high.points) > 640.0  # not confined to a 640-wide space
    assert max(pt.y for pt in high.points) > 400.0

    assert high.points and low.points
    assert abs(len(high.points) - len(low.points)) <= 2

    # Height normalized in ball diameters is resolution independent.
    high_max_h = max(pt.height_diameters for pt in high.points)
    low_max_h = max(pt.height_diameters for pt in low.points)
    assert high_max_h >= 1.5 and low_max_h >= 1.5
    assert abs(high_max_h - low_max_h) <= 0.6

    high_touches = detect_video_touch_events(high)
    low_touches = detect_video_touch_events(low)
    assert len(high_touches) == len(TOUCH_TIMES_MS)
    assert len(low_touches) == len(TOUCH_TIMES_MS)
    for h_evt, gt_ms in zip(high_touches, TOUCH_TIMES_MS, strict=True):
        assert abs(h_evt.t_ms - gt_ms) <= 70


def test_full_hd_tracking_is_fast(tmp_path: Path) -> None:
    """
    Speed guard against removing the downscale: a ~6 s 1920x1080 clip took
    ~3-4 s without it vs ~0.6 s with it (unloaded CPU). Best of two runs and a
    generous budget keep this stable on a busy machine.
    """
    video_path = _clip_path(tmp_path, 1920, 1080, "fullhd")
    elapsed: list[float] = []
    for _ in range(2):
        start = time.perf_counter()
        track = track_ball_in_video(video_path)
        elapsed.append(time.perf_counter() - start)
    assert track.points
    assert min(elapsed) < 2.5, f"1920x1080 tracking took {min(elapsed):.1f}s"


def test_builtin_detector_only_sees_frames_up_to_640px_wide(
    tmp_path: Path, monkeypatch
) -> None:
    """Deterministic guard: the default detector never receives native 1080p frames."""
    seen_widths: set[int] = set()
    real_detect = ClassicalMOG2HoughDetector.detect

    def spy_detect(self, frame_bgr, frame_idx):  # type: ignore[no-untyped-def]
        seen_widths.add(int(frame_bgr.shape[1]))
        return real_detect(self, frame_bgr, frame_idx)

    monkeypatch.setattr(ClassicalMOG2HoughDetector, "detect", spy_detect)
    track = track_ball_in_video(_clip_path(tmp_path, 1280, 720, "spy_720p"))

    assert seen_widths == {640}
    assert (track.frame_width, track.frame_height) == (1280, 720)


def test_small_video_is_not_resized(tmp_path: Path, monkeypatch) -> None:
    """Videos already <= 640 px wide must not go through cv2.resize at all."""
    clip = generate_synthetic_juggling_clip(
        output_dir=tmp_path,
        spec=_spec_for_resolution(640, 360),
        clip_name="native_640x360",
        include_audio=False,
    )
    calls: list[int] = []
    real_resize = cv2.resize

    def spy_resize(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        return real_resize(*args, **kwargs)

    monkeypatch.setattr(cv2, "resize", spy_resize)
    track = track_ball_in_video(clip.video_path)

    assert calls == []
    assert track.points
    assert (track.frame_width, track.frame_height) == (640, 360)
