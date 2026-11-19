"""Policy profiles: how a window's measurements become incidents.

A profile turns a ``WindowObservation`` into a ``WindowAssessment`` (aggregated verdicts plus the ordered
anomaly list). The numeric thresholds behind the measurements live in ``thresholds.py``; this module owns
only the aggregation rules (how many frames make a sustained pose, when a face is absent, ...).
"""
from typing import Any, Callable, Optional, Protocol

from app.services.integrity import thresholds as t
from app.services.integrity.confirm import FlagSample, RunTracker
from app.services.integrity.gaze import GazeRunTracker, normalize_frame_times, sample_from_frame
from app.services.integrity.models import FrameObservation, GazeEvidence, Orientation, WindowAssessment, WindowObservation
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
        self.runs = RunTracker(gaze_runs)
        self.store = gaze_runs

    @staticmethod
    def _frame_evidence(window: WindowObservation) -> GazeEvidence:
        """Evidence for callers that measured frames without timestamps: evenly spread over the window."""
        times = normalize_frame_times(None, len(window.frames), window.duration_ms)
        return GazeEvidence(server=tuple(sample_from_frame(f, at) for f, at in zip(window.frames, times)))

    @staticmethod
    def _frame_times(window: WindowObservation) -> list[int]:
        if len(window.frame_times_ms) == len(window.frames):
            return list(window.frame_times_ms)
        return normalize_frame_times(None, len(window.frames), window.duration_ms)

    def _multiple_faces(
        self, window: WindowObservation, times: list[int], session_key: Optional[str], base: Optional[int]
    ) -> bool:
        """An extra person must persist (S6): two consecutive frames both detectors agree on, or one detector's
        sighting that holds across windows, or a server sighting backed by >= 500 ms of trusted browser telemetry."""
        samples = [FlagSample(at, f.face_count > 1, strong=f.faces_agreed) for f, at in zip(window.frames, times)]
        runs = self.runs.evaluate("multiple_faces", session_key, base, samples)
        if any(
            run.strong_streak >= t.MULTI_FACE_MIN_FRAMES
            or (run.frames >= t.MULTI_FACE_MIN_FRAMES and run.windows >= t.MULTI_FACE_SINGLE_DETECTOR_MIN_WINDOWS)
            for run in runs
        ):
            return True
        return bool(runs) and self._telemetry_sees_extra_face(window, times)

    @staticmethod
    def _telemetry_sees_extra_face(window: WindowObservation, times: list[int]) -> bool:
        """Trusted telemetry with an extra face for >= 500 ms around a server frame that saw one."""
        if window.gaze is None or not window.gaze.client:
            return False
        stretches: list[list[int]] = []
        for sample in sorted(window.gaze.client, key=lambda s: s.t_ms):
            if sample.face_count < 2:
                stretches.append([])
            elif stretches and stretches[-1] and sample.t_ms - stretches[-1][-1] <= t.MULTI_FACE_TELEMETRY_GAP_MS:
                stretches[-1].append(sample.t_ms)
            else:
                stretches.append([sample.t_ms])
        server = [at for frame, at in zip(window.frames, times) if frame.face_count > 1]
        for stretch in stretches:
            if len(stretch) > 1 and stretch[-1] - stretch[0] >= t.MULTI_FACE_TELEMETRY_MIN_MS and any(
                min(abs(at - moment) for moment in stretch) <= t.CLIENT_MATCH_MAX_DT_MS for at in server
            ):
                return True
        return False

    def _face_absent(
        self, frames: tuple[FrameObservation, ...], times: list[int], session_key: Optional[str], base: Optional[int]
    ) -> bool:
        counts = [f.face_count for f in frames]
        empty = sum(1 for c in counts if c == 0)
        if empty and (empty == len(counts) or empty >= max(t.FACE_ABSENT_MIN_EMPTY_FRAMES, len(counts) // 2 + 1)):
            return True
        samples = [FlagSample(at, c == 0) for c, at in zip(counts, times)]
        return any(run.duration_ms >= t.FACE_ABSENT_MIN_RUN_MS for run in self.runs.evaluate(
            "face_absent", session_key, base, samples))

    def _identity(
        self, frames: tuple[FrameObservation, ...], session_key: Optional[str]
    ) -> tuple[Optional[bool], bool]:
        """(reported match, incident). A window is a mismatch when >= 60% of its judged frames do not match;
        the incident needs two such windows in a row (a lone bad window is reported as pending, never as False)."""
        judged = [f.identity_match for f in frames if f.identity_match is not None]
        if not judged:
            return None, False
        bad = sum(1 for match in judged if not match) / len(judged) >= t.IDENTITY_BAD_FRACTION
        stateful = self.store is not None and bool(session_key) and hasattr(self.store, "get_track")
        if not stateful:
            if len(judged) < t.IDENTITY_STATELESS_MIN_FRAMES:
                return None, False
            return (False, True) if bad else (True, False)
        if len(judged) < t.IDENTITY_MIN_ELIGIBLE_FRAMES:
            return None, False
        carried = self.store.get_track(session_key, "identity_bad_windows") or {}
        streak = int(carried.get("windows", 0)) + 1 if bad else 0
        self.store.set_track(session_key, "identity_bad_windows", {"windows": streak} if streak else None)
        if not bad:
            return True, False
        confirmed = streak >= t.IDENTITY_CONFIRM_WINDOWS
        return (False, True) if confirmed else (None, False)

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
            orientations = [f.orientation for f in frames]

            times = self._frame_times(window)
            session_key = window.gaze.session_key if window.gaze else None
            base = window.gaze.window_start_ms if window.gaze else None
            if self._multiple_faces(window, times, session_key, base):
                face_count = max(f.face_count for f in frames)
                anomalies.append("MULTIPLE_FACES")
            elif self._face_absent(frames, times, session_key, base):
                face_count = 0
                anomalies.append("FACE_ABSENT")
            else:
                face_count = 1

            evidence = window.gaze or self._frame_evidence(window)
            verdict = self.gaze.evaluate(evidence)
            anomalies.extend(verdict.kinds)
            if evidence.client_mismatch:
                anomalies.append("CLIENT_MISMATCH")
            head_orientation = verdict.orientation or ("CENTER" if "CENTER" in orientations else orientations[-1])

            identity_match, identity_incident = self._identity(frames, session_key)
            if identity_incident:
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
