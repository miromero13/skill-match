from __future__ import annotations

import math
import wave
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SyntheticJugglingSpec:
    """Configuration for generating a synthetic ball-juggling video and audio clip."""

    duration_s: float = 8.0
    fps: int = 30
    width: int = 640
    height: int = 360
    ball_radius_px: int = 24
    touch_times_ms: list[int] = field(
        default_factory=lambda: [1000, 1800, 2600, 3400, 4200, 5000, 5800, 6600]
    )
    touch_y_px: float = 280.0
    peak_height_diameters: float = 2.2
    background_noise_std: float = 2.0
    missing_frame_ranges: list[tuple[int, int]] = field(default_factory=list)
    audio_offset_ms: int = 0
    audio_sample_rate_hz: int = 48000
    seed: int = 42


@dataclass
class SyntheticClipResult:
    video_path: Path
    audio_path: Path | None
    ground_truth_touch_ms: list[int]
    ball_radius_px: int
    fps: int
    total_frames: int


def _compute_ball_position(
    t_ms: float,
    spec: SyntheticJugglingSpec,
) -> tuple[float, float]:
    """
    Compute `(x_px, y_px)` for timestamp `t_ms` where `y_px` increases downward
    (OpenCV image coordinates). Each touch at `touch_times_ms[k]` is a local
    maximum of `y_px` (`touch_y_px`, i.e., local minimum of height above foot)
    followed by a parabolic flight arc up to `peak_height_diameters`.
    """
    center_x = spec.width * 0.5 + 18.0 * math.sin(t_ms / 900.0)
    sorted_touches = sorted(spec.touch_times_ms)
    if not sorted_touches:
        return center_x, spec.touch_y_px

    diameter_px = float(2 * spec.ball_radius_px)
    amplitude_px = spec.peak_height_diameters * diameter_px

    # Before first touch: descending toward the first touch point
    first_t = float(sorted_touches[0])
    if t_ms <= first_t:
        half_span = max(400.0, first_t)
        dt = first_t - t_ms
        if dt >= half_span:
            return center_x, spec.touch_y_px - amplitude_px
        u = 1.0 - (dt / half_span)  # 0 at apex -> 1 at first touch
        height_above_touch = amplitude_px * (1.0 - u * u)
        return center_x, spec.touch_y_px - height_above_touch

    # Between consecutive touches k and k+1: parabolic arc
    for idx in range(len(sorted_touches) - 1):
        t0 = float(sorted_touches[idx])
        t1 = float(sorted_touches[idx + 1])
        if t0 <= t_ms <= t1:
            span = max(1.0, t1 - t0)
            phase = (t_ms - t0) / span  # 0 at touch k, 0.5 at apex, 1 at touch k+1
            arch = 4.0 * phase * (1.0 - phase)  # 0 -> 1 -> 0
            height_above_touch = amplitude_px * arch
            return center_x, spec.touch_y_px - height_above_touch

    # After last touch: rebound arc and settle
    last_t = float(sorted_touches[-1])
    post_span = 800.0
    dt_after = t_ms - last_t
    if dt_after <= post_span:
        phase = dt_after / post_span
        arch = 4.0 * phase * (1.0 - phase)
        return center_x, spec.touch_y_px - amplitude_px * arch
    return center_x, spec.touch_y_px


def generate_synthetic_audio_wav(
    output_wav_path: Path,
    spec: SyntheticJugglingSpec,
) -> Path:
    """
    Generate a 48 kHz mono WAV file with realistic impact clicks (band 300-2500 Hz)
    at `touch_time_ms + audio_offset_ms`.
    """
    rng = np.random.default_rng(spec.seed)
    sr = spec.audio_sample_rate_hz
    total_samples = int(spec.duration_s * sr)
    signal = rng.normal(0.0, 0.004, size=total_samples).astype(np.float64)

    click_duration_s = 0.025
    click_samples = int(click_duration_s * sr)
    t_vec = np.arange(click_samples, dtype=np.float64) / sr
    envelope = np.exp(-t_vec / 0.005)
    carrier = (
        0.65 * np.sin(2.0 * math.pi * 650.0 * t_vec)
        + 0.35 * np.sin(2.0 * math.pi * 1450.0 * t_vec)
    )
    click_wave = 0.85 * envelope * carrier

    for touch_ms in spec.touch_times_ms:
        impact_ms = touch_ms + spec.audio_offset_ms
        start_idx = int((impact_ms / 1000.0) * sr)
        if 0 <= start_idx < total_samples:
            end_idx = min(total_samples, start_idx + click_samples)
            signal[start_idx:end_idx] += click_wave[: end_idx - start_idx]

    clipped = np.clip(signal, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

    return output_wav_path


def generate_synthetic_juggling_clip(
    output_dir: Path,
    spec: SyntheticJugglingSpec | None = None,
    clip_name: str = "synthetic_juggling",
    include_audio: bool = True,
) -> SyntheticClipResult:
    """
    Render a synthetic `.mp4` video of a bouncing ball with known touch instants
    and optional `.wav` impact audio.
    """
    active_spec = spec or SyntheticJugglingSpec()
    rng = np.random.default_rng(active_spec.seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / f"{clip_name}.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(
        str(video_path),
        fourcc,
        float(active_spec.fps),
        (active_spec.width, active_spec.height),
    )

    total_frames = int(round(active_spec.duration_s * active_spec.fps))
    base_bg = np.full(
        (active_spec.height, active_spec.width, 3),
        (36, 52, 38),
        dtype=np.uint8,
    )
    # Static pitch lines in background so MOG2 learns static scene
    cv2.line(
        base_bg,
        (0, int(active_spec.touch_y_px + active_spec.ball_radius_px + 8)),
        (
            active_spec.width,
            int(active_spec.touch_y_px + active_spec.ball_radius_px + 8),
        ),
        (60, 85, 60),
        2,
    )

    for frame_idx in range(total_frames):
        t_ms = (frame_idx * 1000.0) / float(active_spec.fps)
        frame = base_bg.copy()

        if active_spec.background_noise_std > 0:
            noise = rng.normal(
                0.0, active_spec.background_noise_std, size=frame.shape
            ).astype(np.int16)
            frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        is_occluded = any(
            start_f <= frame_idx <= end_f
            for start_f, end_f in active_spec.missing_frame_ranges
        )

        if not is_occluded:
            bx, by = _compute_ball_position(t_ms, active_spec)
            center = (int(round(bx)), int(round(by)))
            # Draw high-contrast soccer ball (bright white/orange circle with dark border)
            cv2.circle(
                frame,
                center,
                active_spec.ball_radius_px,
                (245, 245, 245),
                -1,
                lineType=cv2.LINE_AA,
            )
            cv2.circle(
                frame,
                center,
                active_spec.ball_radius_px,
                (20, 120, 240),
                2,
                lineType=cv2.LINE_AA,
            )

        writer.write(frame)

    writer.release()

    audio_path: Path | None = None
    if include_audio:
        audio_path = generate_synthetic_audio_wav(
            output_dir / f"{clip_name}.wav", active_spec
        )

    return SyntheticClipResult(
        video_path=video_path,
        audio_path=audio_path,
        ground_truth_touch_ms=sorted(active_spec.touch_times_ms),
        ball_radius_px=active_spec.ball_radius_px,
        fps=active_spec.fps,
        total_frames=total_frames,
    )
