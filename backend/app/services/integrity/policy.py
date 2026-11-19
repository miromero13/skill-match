"""Policy profiles: how a window's measurements become incidents.

A profile turns a ``WindowObservation`` into a ``WindowAssessment`` (aggregated verdicts plus the ordered
anomaly list). The numeric thresholds behind the measurements live in ``thresholds.py``; this module owns
only the aggregation rules (how many frames make a sustained pose, when a face is absent, ...).
"""
from typing import Any, Callable, Optional, Protocol

from app.services.integrity import thresholds as t
from app.services.integrity.gaze import GazeRunTracker, normalize_frame_times, sample_from_frame
from app.services.integrity.models import GazeEvidence, Orientation, WindowAssessment, WindowObservation
from app.services.integrity.sync_analyzer import SyncVerdict, voice_mouth_coexistence

Coexistence = Callable[[bool, bool, bool, int, bool], SyncVerdict]


class PolicyProfile(Protocol):
    """Interface every profile implements; the engine only depends on this."""

    def evaluate(self, window: WindowObservation) -> WindowAssessment:
        """Judges one window."""


class SupervisionProfile:
    """Continuous exam supervision: the window aggregation rules and anomaly codes used since SM-49.

    Where the candidate looks (head and eyes) follows the sustained rule of S5: an incident needs a continuous
    stretch outside the screen zone of at least ``GAZE_TOLERANCE_MS``. ``gaze_runs`` is the session state store
    that lets such a stretch continue across windows; without it each window is judged on its own.
    """

    def __init__(self, coexistence: Coexistence = voice_mouth_coexistence, gaze_runs: Optional[Any] = None) -> None:
        self.coexistence = coexistence
        self.gaze = GazeRunTracker(gaze_runs)

    @staticmethod
    def _frame_evidence(window: WindowObservation) -> GazeEvidence:
        """Evidence for callers that measured frames without timestamps: evenly spread over the window."""
        times = normalize_frame_times(None, len(window.frames), window.duration_ms)
        return GazeEvidence(server=tuple(sample_from_frame(f, at) for f, at in zip(window.frames, times)))

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

            evidence = window.gaze or self._frame_evidence(window)
            verdict = self.gaze.evaluate(evidence)
            anomalies.extend(verdict.kinds)
            if evidence.client_mismatch:
                anomalies.append("CLIENT_MISMATCH")
            head_orientation = verdict.orientation or ("CENTER" if "CENTER" in orientations else orientations[-1])

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
