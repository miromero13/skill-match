"""Policy profiles: how a window's measurements become incidents.

A profile turns a ``WindowObservation`` into a ``WindowAssessment`` (aggregated verdicts plus the ordered
anomaly list). The numeric thresholds behind the measurements live in ``thresholds.py``; this module owns
only the aggregation rules (how many frames make a sustained pose, when a face is absent, ...).
"""
from typing import Any, Callable, Optional, Protocol

from app.services.integrity import thresholds as t
from app.services.integrity.confirm import FlagSample, RunTracker, StreakTracker
from app.services.integrity.gaze import GazeRunTracker, normalize_frame_times, sample_from_frame
from app.services.integrity.models import AudioObservation, FrameObservation, FrameOcclusion, GazeEvidence, Orientation, WindowAssessment, WindowObservation
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
        self.streaks = StreakTracker(gaze_runs)
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

    def _camera_blocked(
        self, frames: tuple[FrameObservation, ...], times: list[int], session_key: Optional[str], base: Optional[int]
    ) -> bool:
        """S8: near-black or flat frames for >= 1 s, or the same image for >= 1.5 s (a static image or looped feed)."""
        dark = self.runs.evaluate(
            "camera_blocked", session_key, base, [FlagSample(at, f.camera_blocked) for f, at in zip(frames, times)])
        frozen = self.runs.evaluate(
            "camera_frozen", session_key, base,
            [FlagSample(at, None if f.frame_delta is None else f.frame_delta <= t.CAMERA_FROZEN_MAX_DIFF)
             for f, at in zip(frames, times)])
        return (any(run.duration_ms >= t.CAMERA_BLOCKED_MIN_MS for run in dark)
                or any(run.duration_ms >= t.CAMERA_FROZEN_MIN_MS for run in frozen))

    def _occlusion(
        self, frames: tuple[FrameObservation, ...], times: list[int], session_key: Optional[str], base: Optional[int]
    ) -> tuple[bool, bool]:
        """S7: a continuous run of covered-face (or covered-mouth) frames of at least 1 s. Frames without a verdict
        (no reference yet, head turned, no single face) neither extend nor end a run; a face cover includes the mouth."""
        def verdicts(pick: Callable[[FrameOcclusion], bool]) -> list[FlagSample]:
            return [
                FlagSample(at, pick(f.occlusion) if f.occlusion is not None and f.occlusion.measured else None)
                for f, at in zip(frames, times)
            ]

        def confirmed(name: str, pick: Callable[[FrameOcclusion], bool]) -> bool:
            return any(run.duration_ms >= t.OCC_MIN_RUN_MS
                       for run in self.runs.evaluate(name, session_key, base, verdicts(pick)))

        face = confirmed("occlusion_face", lambda o: o.face)
        mouth = confirmed("occlusion_mouth", lambda o: o.mouth or o.face)
        return face, mouth and not face

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

    def _multiple_speakers(self, audio: AudioObservation, session_key: Optional[str]) -> bool:
        """S2: voices overlapping >= 0.3 s or a foreign cluster next to the enrolled voice are confirmed at once;
        several speakers otherwise need two diarizations in a row (a window without speech resets the count)."""
        if audio.foreign_voice or audio.overlap_s >= t.MULTI_SPEAKER_IMMEDIATE_OVERLAP_S:
            self.streaks.update("multi_speakers", session_key, True)
            return True
        if not audio.speech_detected:
            flag: Optional[bool] = False
        elif not audio.diarized:
            flag = None  # no diarization ran (too little speech yet): neither extends nor resets
        else:
            flag = audio.multiple_speakers
        return self.streaks.update("multi_speakers", session_key, flag) >= t.MULTI_SPEAKER_CONFIRM_EVALUATIONS

    def _streak(self, name: str, session_key: Optional[str], audio: AudioObservation, flag: Optional[bool]) -> int:
        """Consecutive evaluations that were flagged. A long silence (the voiced buffer was forgotten) restarts it."""
        return self.streaks.update(name, session_key, False if audio.voice_reset else flag)

    def _voice_ownership(self, audio: AudioObservation, session_key: Optional[str], anomalies: list[str]) -> Optional[bool]:
        """S3 / S11: the voice must be the enrolled one. A mismatch needs two evaluations in a row (VOICE_MISMATCH);
        speech with no voiceprint is VOICE_UNVERIFIED once it persists (never a clean pass by omission). Under one
        second of voiced speech there is no verdict and the counts are left alone."""
        status = audio.voice_status
        mismatch = self._streak(
            "voice_mismatch", session_key, audio,
            None if status in (None, "insufficient", "unenrolled") else status == "mismatch",
        )
        unverified = self._streak(
            "voice_unverified", session_key, audio, None if status in (None, "insufficient") else status == "unenrolled",
        )
        if mismatch >= t.VOICE_CONFIRM_EVALUATIONS:
            anomalies.append("VOICE_MISMATCH")
        if unverified >= t.VOICE_CONFIRM_EVALUATIONS:
            anomalies.append("VOICE_UNVERIFIED")
        return {"match": True, "mismatch": False}.get(status or "")

    def _background_audio(self, audio: AudioObservation, session_key: Optional[str], base: Optional[int]) -> bool:
        """S4: non-speech audio above the calibrated ambient floor, continuously for >= 2 s (across windows too)."""
        samples = [FlagSample(round((i + 0.5) * 1000 * t.VAD_CHUNK_SAMPLES / t.AUDIO_SAMPLE_RATE), flag)
                   for i, flag in enumerate(audio.background_flags)]
        return any(run.duration_ms >= t.BACKGROUND_MIN_MS
                   for run in self.runs.evaluate("background_audio", session_key, base, samples))

    def evaluate(self, window: WindowObservation) -> WindowAssessment:
        anomalies: list[str] = []
        face_count = 1
        head_orientation: Orientation = "CENTER"
        identity_match: Optional[bool] = None
        camera_blocked = occlusion_face = occlusion_mouth = False
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
            camera_blocked = self._camera_blocked(frames, times, session_key, base)
            if self._multiple_faces(window, times, session_key, base):
                face_count = max(f.face_count for f in frames)
                anomalies.append("MULTIPLE_FACES")
            elif camera_blocked:
                # A covered or frozen camera is reported as such, not also as an absent face.
                face_count = 0 if all(f.face_count == 0 for f in frames) else 1
            elif self._face_absent(frames, times, session_key, base):
                face_count = 0
                anomalies.append("FACE_ABSENT")
            else:
                face_count = 1
            if camera_blocked:
                anomalies.append("CAMERA_BLOCKED")
            occlusion_face, occlusion_mouth = self._occlusion(frames, times, session_key, base)
            if occlusion_face:
                anomalies.append("FACE_OCCLUDED")
            if occlusion_mouth:
                anomalies.append("MOUTH_OCCLUDED")

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
        audio_key = window.gaze.session_key if window.gaze else None
        audio_base = window.gaze.window_start_ms if window.gaze else None
        if self._background_audio(audio, audio_key, audio_base):
            anomalies.append("BACKGROUND_AUDIO")
        multiple_speakers = self._multiple_speakers(audio, audio_key)

        mouth_covered = occlusion_mouth or occlusion_face
        verdict = self.coexistence(
            audio.speech_detected, multiple_speakers, visual_unavailable, face_count, window.mouth_moving
        )
        lip_sync = window.lip_sync.verdict if audio.speech_detected else None
        if audio.speech_detected and not multiple_speakers and not visual_unavailable and face_count == 1:
            if mouth_covered:
                verdict = SyncVerdict(False, "VOICE_DETECTED")  # a covered mouth is no mouth evidence
            elif window.lip_sync.verdict != "insufficient":
                # Real evidence: voice energy vs mouth aperture over time (S3, S11) replaces plain coexistence.
                verdict = SyncVerdict(window.lip_sync.verdict == "synced")
            # else: no usable mouth series (no telemetry, sparse frames): the coexistence verdict stands
        lip_confirmed = self._streak(
            "lip_sync", audio_key, audio,
            None if lip_sync in (None, "insufficient") or verdict.anomaly or multiple_speakers or mouth_covered
            or face_count != 1 else lip_sync == "unsynced",
        ) >= t.LIPSYNC_CONFIRM_EVALUATIONS
        if verdict.anomaly:
            anomalies.append(verdict.anomaly)
        elif lip_confirmed:
            anomalies.append("LIP_SYNC_MISMATCH")
        voice_match = self._voice_ownership(audio, audio_key, anomalies)
        if audio.speaker_model_unavailable and "MODEL_UNAVAILABLE" not in anomalies:
            anomalies.append("MODEL_UNAVAILABLE")  # speech that could not be checked is never a clean audio verdict

        return WindowAssessment(
            face_count=face_count,
            head_orientation=head_orientation,
            identity_match=identity_match,
            speech_detected=audio.speech_detected,
            mouth_moving=window.mouth_moving,
            mouth_sync=verdict.mouth_sync,
            multiple_speakers=multiple_speakers,
            noise_level=audio.noise_level,
            anomalies=anomalies,
            occlusion_face=occlusion_face,
            occlusion_mouth=occlusion_mouth,
            camera_blocked=camera_blocked,
            voice_match=voice_match,
            lip_sync=lip_sync,  # type: ignore[arg-type]
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
