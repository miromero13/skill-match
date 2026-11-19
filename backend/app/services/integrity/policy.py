"""Policy profiles: how a window's measurements become incidents.

A profile turns a ``WindowObservation`` into a ``WindowAssessment`` (aggregated verdicts plus the ordered
anomaly list). The numeric thresholds behind the measurements live in ``thresholds.py``; this module owns
only the aggregation rules (how many frames make a sustained pose, when a face is absent, ...).
"""
from typing import Callable, Optional, Protocol

from app.services.integrity import thresholds as t
from app.services.integrity.models import Orientation, WindowAssessment, WindowObservation
from app.services.integrity.sync_analyzer import SyncVerdict, voice_mouth_coexistence

Coexistence = Callable[[bool, bool, bool, int, bool], SyncVerdict]


class PolicyProfile(Protocol):
    """Interface every profile implements; the engine only depends on this."""

    def evaluate(self, window: WindowObservation) -> WindowAssessment:
        """Judges one window."""


class SupervisionProfile:
    """Continuous exam supervision: the window aggregation rules and anomaly codes used since SM-49."""

    def __init__(self, coexistence: Coexistence = voice_mouth_coexistence) -> None:
        self.coexistence = coexistence

    def evaluate(self, window: WindowObservation) -> WindowAssessment:
        anomalies: list[str] = []
        face_count = 1
        head_orientation: Orientation = "CENTER"
        identity_match: Optional[bool] = None
        frames = window.frames
        visual_unavailable = window.visual_unavailable

        if window.video_missing:
            anomalies.append("VIDEO_MISSING")
        if window.model_unavailable:
            anomalies.append("MODEL_UNAVAILABLE")
        if visual_unavailable:
            face_count = 0
            head_orientation = "UNKNOWN"

        if frames:
            counts = [f.face_count for f in frames]
            orientations = [f.orientation for f in frames]
            identities = [f.identity_match for f in frames if f.identity_match is not None]

            if all(c == 0 for c in counts) or sum(1 for c in counts if c == 0) >= max(
                t.FACE_ABSENT_MIN_EMPTY_FRAMES, len(counts) // 2 + 1
            ):
                face_count = 0
                anomalies.append("FACE_ABSENT")
            elif any(c > 1 for c in counts):
                face_count = max(counts)
                anomalies.append("MULTIPLE_FACES")
            else:
                face_count = 1

            down_count = sum(1 for o in orientations if o == "DOWN")
            side_frames = [o for o in orientations if o in ("LEFT", "RIGHT")]

            min_sustained = 1 if len(orientations) == 1 else max(2, len(orientations) // 2)
            if down_count >= min_sustained:
                head_orientation = "DOWN"
                anomalies.append("HEAD_POSE_DOWN")
            elif len(side_frames) >= min_sustained:
                head_orientation = side_frames[-1]
                anomalies.append("HEAD_POSE_SIDE")
            else:
                head_orientation = "CENTER" if "CENTER" in orientations else orientations[-1]

            if identities:
                identity_match = all(identities)
                if identity_match is False:
                    anomalies.append("IDENTITY_MISMATCH")

        audio = window.audio
        if window.audio_missing:
            anomalies.append("AUDIO_MISSING")
        if audio.high_noise:
            anomalies.append("HIGH_NOISE")

        verdict = self.coexistence(
            audio.speech_detected, audio.multiple_speakers, visual_unavailable, face_count, window.mouth_moving
        )
        if verdict.anomaly:
            anomalies.append(verdict.anomaly)

        return WindowAssessment(
            face_count=face_count,
            head_orientation=head_orientation,
            identity_match=identity_match,
            speech_detected=audio.speech_detected,
            mouth_moving=window.mouth_moving,
            mouth_sync=verdict.mouth_sync,
            multiple_speakers=audio.multiple_speakers,
            noise_level=audio.noise_level,
            anomalies=anomalies,
        )


class CalibrationProfile:
    """Pre-exam calibration: skeleton only, filled by T9.

    Calibration asks the same questions as supervision (one face, centered, one voice, no noise) but as
    guided steps that must *pass* instead of incidents to log: look at each screen corner (gaze zone),
    stay silent, read a phrase (voiceprint capture). T9 implements ``evaluate`` to return a
    ``WindowAssessment`` whose anomalies mean "step not passed", reusing the same engine and analyzers.
    """

    def evaluate(self, window: WindowObservation) -> WindowAssessment:
        raise NotImplementedError("CalibrationProfile is implemented by T9; use SupervisionProfile for now.")
