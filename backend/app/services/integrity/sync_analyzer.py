"""Mouth movement and voice/mouth coexistence.

Coexistence is now only the fallback: when a window has no usable mouth series (no trusted telemetry, sparse
frames) the policy still uses it; with a series, ``lipsync.evaluate`` (temporal correlation, T8) decides.

Calibration mapping (T9): ``CalibrationAVService`` (voice + mouth together) maps to ``voice_mouth_coexistence``.
"""
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import FrameObservation, MouthPatch


@dataclass(frozen=True)
class SyncVerdict:
    """``mouth_sync`` is None when it cannot be assessed; ``anomaly`` is the incident code it implies."""

    mouth_sync: Optional[bool] = None
    anomaly: Optional[str] = None


def voice_mouth_coexistence(
    speech_detected: bool,
    multiple_speakers: bool,
    visual_unavailable: bool,
    face_count: int,
    mouth_moving: bool,
) -> SyncVerdict:
    """Speech is only coherent when exactly one visible face moves its mouth while the voice is present."""
    if not speech_detected:
        return SyncVerdict()
    if multiple_speakers:
        return SyncVerdict(False, "MULTIPLE_SPEAKERS")
    if visual_unavailable:
        return SyncVerdict()  # lip-sync cannot be assessed without a vision model
    if face_count == 1 and mouth_moving:
        return SyncVerdict(True)
    return SyncVerdict(False, "VOICE_DETECTED")


class SyncAnalyzer:
    """Decides whether the mouth moved during a window from per-frame observations."""

    def mouth_movement(self, frames: Sequence[FrameObservation]) -> tuple[bool, list[float]]:
        """Returns (moving, patch movements). Uses 3D aperture scores when MediaPipe ran, else the patch trace."""
        mouth_open_scores = [float(f.mouth_open_score) for f in frames]
        if any(s > 0.0 for s in mouth_open_scores):
            max_open = max(mouth_open_scores)
            min_open = min(mouth_open_scores)
            open_frames = sum(1 for s in mouth_open_scores if s >= t.MOUTH_OPEN_FRAME_SCORE)
            dynamic_range = max_open - min_open
            moving = max_open >= t.MOUTH_MIN_PEAK_SCORE and (
                dynamic_range >= t.MOUTH_MIN_DYNAMIC_RANGE or open_frames >= t.MOUTH_MIN_OPEN_FRAMES
            )
            return moving, []
        return self.compute_mouth_trace([f.mouth_patch for f in frames])

    @staticmethod
    def compute_mouth_trace(patches: Sequence[Optional[MouthPatch]]) -> tuple[bool, list[float]]:
        """Inter-frame cheek-compensated mouth movements (fallback when only YuNet patches exist)."""
        valid = [p for p in patches if p is not None]
        if len(valid) < 2:
            return False, []

        movements: list[float] = []
        for idx in range(1, len(valid)):
            prev_mouth, prev_cheeks = valid[idx - 1]
            curr_mouth, curr_cheeks = valid[idx]

            pm = prev_mouth - float(prev_mouth.mean())
            cm = curr_mouth - float(curr_mouth.mean())
            pc = prev_cheeks - float(prev_cheeks.mean())
            cc = curr_cheeks - float(curr_cheeks.mean())

            mouth_diff = float(np.mean(np.abs(cm - pm))) / 255.0
            cheek_diff = float(np.mean(np.abs(cc - pc))) / 255.0
            net_motion = max(0.0, mouth_diff - 1.0 * cheek_diff)

            center_prev = pm[6:22, 8:32]
            center_curr = cm[6:22, 8:32]
            mouth_std_delta = abs(float(center_curr.std()) - float(center_prev.std())) / 255.0
            cheek_std_delta = abs(float(cc.std()) - float(pc.std())) / 255.0
            net_std_delta = max(0.0, mouth_std_delta - 1.0 * cheek_std_delta)

            movements.append(max(net_motion, net_std_delta * 0.85))

        if not movements:
            return False, []

        max_mov = max(movements)
        mean_mov = float(np.mean(movements))
        active_steps = sum(1 for m in movements if m >= t.MOUTH_PATCH_ACTIVE_STEP)
        moving = (max_mov >= t.MOUTH_PATCH_PEAK and mean_mov >= t.MOUTH_PATCH_MEAN) or (
            active_steps >= t.MOUTH_PATCH_MIN_ACTIVE_STEPS
        )
        return moving, movements
