from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks, resample_poly, stft

from app.football.config import AudioEventsConfig, load_football_config


@dataclass
class AudioImpactEvent:
    t_ms: int
    strength: float
    confidence: float


class AudioImpactClassifierProtocol(Protocol):
    """
    Swappable interface for the future small CNN trained on Mel windows (Phase 7).
    When no trained model is active, the spectral flux + MAD heuristic is used.
    """

    def score_window(self, mel_window: np.ndarray) -> float:
        """Return probability `[0.0, 1.0]` that `mel_window` is a ball touch impact."""


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _build_mel_filterbank(
    sample_rate: int,
    n_fft: int,
    n_mels: int = 32,
    fmin: float = 200.0,
    fmax: float = 4000.0,
) -> np.ndarray:
    """Construct a triangular Mel filterbank matrix of shape `(n_mels, n_fft // 2 + 1)`."""
    mel_min = _hz_to_mel(fmin)
    mel_max = _hz_to_mel(min(fmax, sample_rate / 2.0))
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = np.array([_mel_to_hz(float(m)) for m in mel_points], dtype=np.float64)

    fft_freqs = np.linspace(0.0, sample_rate / 2.0, n_fft // 2 + 1)
    filterbank = np.zeros((n_mels, len(fft_freqs)), dtype=np.float64)

    for i in range(n_mels):
        f_left = hz_points[i]
        f_center = hz_points[i + 1]
        f_right = hz_points[i + 2]

        left_mask = (fft_freqs >= f_left) & (fft_freqs <= f_center)
        right_mask = (fft_freqs >= f_center) & (fft_freqs <= f_right)

        if f_center > f_left:
            filterbank[i, left_mask] = (fft_freqs[left_mask] - f_left) / (
                f_center - f_left
            )
        if f_right > f_center:
            filterbank[i, right_mask] = (f_right - fft_freqs[right_mask]) / (
                f_right - f_center
            )

    return filterbank


def load_mono_48khz_wav(
    audio_path: str | Path,
    target_sr: int = 48000,
) -> tuple[np.ndarray, int]:
    """Load a `.wav` file, convert to mono float64 in `[-1, 1]`, and resample to `target_sr`."""
    sr, data = wavfile.read(str(audio_path))
    arr = np.asarray(data)

    if arr.ndim > 1:
        arr = arr.mean(axis=1)

    if np.issubdtype(arr.dtype, np.integer):
        max_val = float(np.iinfo(arr.dtype).max)
        waveform = arr.astype(np.float64) / max(1.0, max_val)
    else:
        waveform = arr.astype(np.float64)

    if int(sr) != target_sr:
        gcd = math.gcd(int(sr), target_sr)
        up = target_sr // gcd
        down = int(sr) // gcd
        waveform = np.asarray(resample_poly(waveform, up, down), dtype=np.float64)

    return waveform, target_sr


def detect_audio_impact_events(
    audio_path: str | Path,
    config: AudioEventsConfig | None = None,
    classifier: AudioImpactClassifierProtocol | None = None,
    min_separation_ms: int = 180,
) -> list[AudioImpactEvent]:
    """
    Pure pipeline step (`audio_events`):
    audio (`.wav`) -> list of `AudioImpactEvent`.
    Computes a 48 kHz mono Mel spectrogram in band `[band_low_hz, band_high_hz]`,
    extracts positive spectral flux, and picks impact peaks above `median + k * MAD`.
    """
    cfg = config or load_football_config().audio_events
    waveform, sr = load_mono_48khz_wav(audio_path, target_sr=cfg.sample_rate_hz)
    if len(waveform) < 1024:
        return []

    n_fft = 1024
    hop_length = 240  # 5 ms hop at 48 kHz for high temporal precision
    _, _, zxx = stft(
        waveform,
        fs=sr,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        boundary=None,
        padded=False,
    )
    mag_spec = np.abs(zxx)
    if mag_spec.shape[1] < 3:
        return []

    mel_fb = _build_mel_filterbank(
        sample_rate=sr,
        n_fft=n_fft,
        n_mels=32,
        fmin=cfg.band_low_hz,
        fmax=cfg.band_high_hz,
    )
    mel_spec = mel_fb @ (mag_spec**2)
    log_mel = np.log1p(1000.0 * mel_spec)

    # Positive spectral flux across consecutive frames
    diff = np.diff(log_mel, axis=1, prepend=log_mel[:, :1])
    pos_diff = np.maximum(0.0, diff)
    spectral_flux = np.sum(pos_diff, axis=0)

    median_flux = float(np.median(spectral_flux))
    mad_flux = float(np.median(np.abs(spectral_flux - median_flux)))
    # Robust threshold: median + k * MAD (with small floor to ignore silence)
    threshold = max(median_flux + cfg.mad_k * max(mad_flux, 1e-4), 0.15)

    frame_duration_ms = (hop_length * 1000.0) / float(sr)
    min_distance_frames = max(1, round(min_separation_ms / frame_duration_ms))

    peaks, _ = find_peaks(
        spectral_flux,
        height=threshold,
        distance=min_distance_frames,
    )

    events: list[AudioImpactEvent] = []
    for p_idx in peaks:
        idx = int(p_idx)
        t_ms = round(idx * frame_duration_ms)
        strength = float(spectral_flux[idx])
        snr_ratio = strength / max(threshold, 1e-6)
        base_conf = min(1.0, max(0.55, 0.50 + 0.25 * min(2.0, snr_ratio - 1.0)))

        if classifier is not None:
            w_start = max(0, idx - 4)
            w_end = min(log_mel.shape[1], idx + 5)
            clf_prob = classifier.score_window(log_mel[:, w_start:w_end])
            base_conf = 0.5 * base_conf + 0.5 * float(clf_prob)

        events.append(
            AudioImpactEvent(
                t_ms=t_ms,
                strength=round(strength, 4),
                confidence=round(base_conf, 4),
            )
        )

    return events
