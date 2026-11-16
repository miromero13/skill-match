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
    touch_peak_heights_diameters: list[float] | None = None
    touch_y_px: float = 280.0
    peak_height_diameters: float = 2.2
    background_noise_std: float = 2.0
    missing_frame_ranges: list[tuple[int, int]] = field(default_factory=list)
    audio_offset_ms: int = 0
    audio_drift_ms_per_min: float = 0.0
    custom_audio_touch_times_ms: list[int] | None = None
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

    # Before first touch: descending from apex toward the first touch point
    first_t = float(sorted_touches[0])
    if t_ms <= first_t:
        half_span = 400.0
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
            arc_diameters = (
                spec.touch_peak_heights_diameters[idx]
                if (
                    spec.touch_peak_heights_diameters is not None
                    and idx < len(spec.touch_peak_heights_diameters)
                )
                else spec.peak_height_diameters
            )
            height_above_touch = (arc_diameters * diameter_px) * arch
            return center_x, spec.touch_y_px - height_above_touch

    # After last touch: ball rebounds up to apex and stays held/caught at apex
    last_t = float(sorted_touches[-1])
    half_span = 400.0
    dt_after = t_ms - last_t
    if dt_after <= half_span:
        u = 1.0 - (dt_after / half_span)  # 1 at last touch -> 0 at apex
        height_above_touch = amplitude_px * (1.0 - u * u)
        return center_x, spec.touch_y_px - height_above_touch
    return center_x, spec.touch_y_px - amplitude_px


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

    audio_touches = (
        spec.custom_audio_touch_times_ms
        if spec.custom_audio_touch_times_ms is not None
        else spec.touch_times_ms
    )
    for touch_ms in audio_touches:
        drift_ms = (touch_ms / 60000.0) * spec.audio_drift_ms_per_min
        impact_ms = touch_ms + spec.audio_offset_ms + drift_ms
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

    total_frames = round(active_spec.duration_s * active_spec.fps)
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
            center = (round(bx), round(by))
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


def build_synthetic_spec_for_plan(
    segments_plan: list[dict[str, int | str]],
    seed: int = 777,
) -> SyntheticJugglingSpec:
    """
    Build a `SyntheticJugglingSpec` whose touch intervals and heights obey
    every segment in `segments_plan`:
    - LOW: height = 1.0 diameters (< 1.5), interval = 750 ms
    - HIGH: height = 3.5 diameters (> 3.0), interval = 900 ms
    - SLOW: height = 2.0 diameters, interval = 1250 ms (> 1.0 s)
    - FAST: height = 1.6 diameters, interval = 450 ms (< 0.6 s)
    """
    touch_times: list[int] = []
    peak_heights: list[float] = []
    total_duration_ms = 0

    for seg in sorted(segments_plan, key=lambda s: int(s["indice"])):
        tipo = str(seg["tipo"]).upper()
        start_ms = int(seg["inicio_servidor_ms"])
        dur_ms = int(seg["duracion_ms"])
        end_ms = start_ms + dur_ms
        total_duration_ms = max(total_duration_ms, end_ms)

        if tipo == "LOW":
            interval_ms = 750
            height_diam = 1.0
        elif tipo == "HIGH":
            interval_ms = 900
            height_diam = 3.5
        elif tipo == "SLOW":
            interval_ms = 1250
            height_diam = 2.0
        else:  # FAST
            interval_ms = 450
            height_diam = 1.6

        # First touch inside segment occurs ~280 ms after command (realistic human reaction)
        t_cur = max(start_ms + 280, (touch_times[-1] + interval_ms) if touch_times else start_ms + 280)
        while t_cur <= end_ms - 150:
            touch_times.append(t_cur)
            peak_heights.append(height_diam)
            t_cur += interval_ms

    return SyntheticJugglingSpec(
        duration_s=(total_duration_ms + 900) / 1000.0,
        touch_times_ms=touch_times,
        touch_peak_heights_diameters=peak_heights,
        seed=seed,
    )
