"""Temporal lip-sync: does the voice follow the mouth? (S3, S11)

The speech energy envelope (RMS per 30 ms chunk, voiced chunks only) is compared with the mouth aperture
over the same timeline:

  * ``correlation``: the best normalized cross-correlation over a lag window of about -100 ... +300 ms (camera
    and microphone are never perfectly aligned), after smoothing the envelope to the pace of a jaw;
  * ``overlap``: the fraction of voiced time during which the mouth aperture is actually varying.

Verdicts: ``synced``; ``unsynced`` (voice with a still mouth, or a voice that does not follow the mouth, e.g. a
played recording or somebody else speaking); ``insufficient`` (too little speech, or too few mouth readings to
judge): never a pass by omission.

The mouth series is the browser's ~15 fps telemetry when it is trusted, else the sampled JPEG frames the server
measured itself. The aperture formula is shared with the browser (``gaze-tracking.ts``), see ``mouth_open_score``
in ``frame_analyzer.py``.
"""
import math
from typing import Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import LipSyncResult

CHUNK_MS = 1000.0 * t.VAD_CHUNK_SAMPLES / t.AUDIO_SAMPLE_RATE  # 30 ms
INSUFFICIENT = LipSyncResult()


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denominator = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
    # A flat series has no variation to correlate: 0, never a lucky 1.
    return float(np.dot(a, b) / denominator) if denominator > 1e-9 else 0.0


def _local_range(values: np.ndarray, half: int) -> np.ndarray:
    return np.array([float(np.ptp(values[max(0, i - half): i + half + 1])) for i in range(values.size)])


def evaluate(
    chunk_rms: Sequence[float],
    voiced_flags: Sequence[bool],
    mouth: Sequence[tuple[int, float]],
    source: Optional[str],
) -> LipSyncResult:
    """Verdict for one window: ``mouth`` is (ms from the window start, aperture) readings of one face."""
    count = min(len(chunk_rms), len(voiced_flags))
    if count == 0:
        return INSUFFICIENT
    voiced = np.asarray(list(voiced_flags)[:count], dtype=bool)
    if float(voiced.sum()) * CHUNK_MS < t.LIPSYNC_MIN_VOICED_MS:
        return INSUFFICIENT

    readings = sorted((int(at), float(value)) for at, value in mouth if math.isfinite(value))
    if len(readings) < t.LIPSYNC_MIN_MOUTH_SAMPLES or readings[-1][0] - readings[0][0] < t.LIPSYNC_MIN_MOUTH_SPAN_MS:
        return INSUFFICIENT
    mouth_t = np.array([at for at, _ in readings], dtype=np.float64)
    mouth_v = np.array([value for _, value in readings], dtype=np.float64)

    centers = (np.arange(count) + 0.5) * CHUNK_MS
    energy = np.where(voiced, np.asarray(list(chunk_rms)[:count], dtype=np.float64), 0.0)
    kernel = np.ones(t.LIPSYNC_SMOOTH_CHUNKS) / t.LIPSYNC_SMOOTH_CHUNKS
    energy = np.convolve(energy, kernel, mode="same")

    best: Optional[tuple[float, int, np.ndarray, np.ndarray]] = None
    for lag in t.LIPSYNC_LAGS_MS:
        at = centers + lag
        valid = (at >= mouth_t[0]) & (at <= mouth_t[-1])
        if valid.sum() < t.LIPSYNC_MIN_VALID_FRACTION * count or (valid & voiced).sum() == 0:
            continue
        shifted = np.interp(at, mouth_t, mouth_v)
        score = _pearson(energy[valid], shifted[valid])
        if best is None or score > best[0]:
            best = (score, lag, shifted, valid)
    if best is None:
        return INSUFFICIENT
    correlation, lag, shifted, valid = best

    half = max(1, int(round(t.LIPSYNC_ACTIVITY_HALF_WINDOW_MS / CHUNK_MS)))
    varying = _local_range(shifted, half) >= t.LIPSYNC_ACTIVITY_MIN_RANGE
    judged = voiced & valid
    overlap = float((varying & judged).sum() / judged.sum())

    synced = overlap >= t.LIPSYNC_MIN_ACTIVITY_OVERLAP and correlation >= t.LIPSYNC_MIN_CORRELATION
    return LipSyncResult("synced" if synced else "unsynced", correlation, overlap, int(lag), source)
