"""Pre-exam calibration on the integrity engine (T9 / S9): the same analyzers and thresholds as supervision.

``CalibrationProfile`` is the calibration counterpart of ``SupervisionProfile``: it turns the engine's measurements into
named pass/fail checks, each with a Spanish reason, instead of incidents to log. ``CalibrationEngine`` measures the
evidence of every guided step with the shared ``FrameAnalyzer`` / ``AudioAnalyzer`` and stops at the first failing check:

  movement   one confirmed face, camera not blocked or frozen, face and mouth uncovered, identity, frontal pose and
             gaze, and the requested head turn measured with the 3D pose (never the 2D landmark ratios)
  gaze zone  the centre and the four corners (``gaze.compute_zone``)
  silence    the VAD hears no speech and the ambient floor is low
  speech     enough voiced speech, one voice (diarization), no speech in the final pause
  voice      the browser's mouth telemetry agrees with the server's own frames, the voice follows the mouth
             (lip-sync) and the voiceprint is consistent

It produces what supervision needs: the gaze zone, the voiceprint with the ambient floor and the occlusion reference.
A missing model fails closed (``CalibrationRejected`` with status 503), never a pass.
"""
import hashlib
import statistics
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np

from app.services.integrity import enrollment, environment, messages as m, thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.audio_analyzer import AudioAnalyzer, run_stats, signal_rms
from app.services.integrity.confirm import FlagSample, RunTracker, longest
from app.services.integrity.frame_analyzer import FrameAnalyzer, create_vision_models, decode_frame
from app.services.integrity.gaze import (
    DEFAULT_ZONE, IN, TARGETS, GazeCalibrationError, classify, compute_zone, sample_from_frame,
)
from app.services.integrity.models import AudioObservation, FrameBatch, FrameObservation, GazeZone
from app.services.integrity.state import InMemoryStateStore, SessionStateStore

# Every check a calibration must pass; READY_FOR_THEORY requires all of them.
REQUIRED_CHECKS = frozenset({
    "lighting", "sharpness", "framing", "passive_screen_check", "camera_live", "single_face", "face_uncovered",
    "mouth_uncovered", "identity", "frontal", "liveness", "occlusion_reference", "gaze_zone",
    "background_quiet", "microphone", "speech_pause", "single_speaker", "no_overlap",
    "mouth_telemetry", "mouth_audio_sync", "voiceprint",
})
# The checks whose evidence the pre-exam request does not carry yet (the zone points and the browser telemetry).
NEW_CONTRACT_CHECKS = frozenset({"gaze_zone", "mouth_telemetry", "voiceprint"})


class CalibrationRejected(Exception):
    """A calibration step failed: ``check`` names it, ``message`` is shown verbatim, ``status`` is 400 or 503."""

    def __init__(self, check: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.check, self.message, self.status = check, message, status


@dataclass(frozen=True)
class CalibrationCheck:
    name: str
    passed: bool
    reason: str = ""  # Spanish, shown verbatim when the check failed
    status: int = 400  # 503 when the check could not run for lack of a model


@dataclass(frozen=True)
class CalibrationEvidence:
    """Everything the member's guided calibration captured."""

    action: str  # TURN_LEFT / TURN_RIGHT
    frames: Sequence[str]  # liveness frames, about one second apart (base64 JPEG)
    gaze_points: Optional[Mapping[str, Sequence[str]]]  # target -> frames; None: the contract that predates the zone
    audio: Sequence[float]  # silence segment + speech segment, 16 kHz mono
    ambient_ms: int  # length of the silence segment
    voice_frames: Sequence[tuple[int, str]]  # (ms from the recording start, base64 JPEG) of the speech segment
    mouth: Optional[Sequence[tuple[int, float]]]  # browser mouth readings, ms from the recording start; None: none sent
    reference: np.ndarray  # the enrolled face embedding (unit vector)
    camera_label: str = ""  # client-supplied, advisory (see environment.py)

    @property
    def complete(self) -> bool:
        """False for the pre-exam contract that predates the zone and the browser telemetry (removed next slice)."""
        return self.gaze_points is not None and self.mouth is not None


@dataclass(frozen=True)
class CalibrationOutput:
    """The verdict and what supervision needs from it. The zone, voiceprint and reference never leave the server."""

    checks: dict[str, bool]
    gaze_zone: Optional[GazeZone]  # None only for an incomplete-contract evidence
    voiceprint: Optional[dict[str, Any]]
    occlusion_ref: dict[str, float]


def _fail(check: str, reason: str, status: int = 400) -> CalibrationCheck:
    return CalibrationCheck(check, False, reason, status)


def _ok(check: str) -> CalibrationCheck:
    return CalibrationCheck(check, True)


def _verdict(check: str, passed: bool, reason: str) -> CalibrationCheck:
    return _ok(check) if passed else _fail(check, reason)


class CalibrationProfile:
    """Judges calibration measurements: each method returns its named checks (a failed one carries its reason)."""

    # ---- the movement step ---------------------------------------------------------------------

    def camera(
        self, frames: Sequence[FrameObservation], digests: int, virtual_label: bool,
        envs: Sequence[environment.FrameEnvironment], times: Sequence[int],
    ) -> list[CalibrationCheck]:
        """Lighting, focus, framing, screen texture and a live (not blocked, frozen or virtual) camera."""
        blocked = longest(RunTracker().evaluate(
            "blocked", None, None, [FlagSample(at, f.camera_blocked) for f, at in zip(frames, times)]))
        frozen = longest(RunTracker().evaluate(
            "frozen", None, None,
            [FlagSample(at, None if f.frame_delta is None else f.frame_delta <= t.CAMERA_FROZEN_MAX_DIFF)
             for f, at in zip(frames, times)]))
        lighting = _verdict("lighting", all(environment.lighting_ok(e) for e in envs), m.LIGHTING)
        if not lighting.passed or not all(f.face_count == 1 for f in frames):
            # Lighting first, then exactly one face: the other checks need a well-lit single face to mean anything.
            return [lighting] if not lighting.passed else [lighting, _fail("single_face", m.SINGLE_FACE)]
        live: CalibrationCheck = _ok("camera_live")
        if virtual_label:
            live = _fail("camera_live", m.PHYSICAL_CAMERA)
        elif digests < min(t.CAL_MIN_DISTINCT_FRAMES, len(frames)) or frozen >= t.CAMERA_FROZEN_MIN_MS:
            live = _fail("camera_live", m.CAMERA_FROZEN if frozen >= t.CAMERA_FROZEN_MIN_MS else m.DIFFERENT_FRAMES)
        elif any(f.camera_blocked for f in frames) or blocked >= t.CAMERA_BLOCKED_MIN_MS:
            live = _fail("camera_live", m.CAMERA_BLOCKED)
        return [
            lighting,
            live,
            _verdict("framing", all(environment.framing_ok(f.face_box, f.face_score) for f in frames), m.FRAMING),
            _verdict("sharpness", all(environment.sharp_ok(e) for e in envs), m.SHARPNESS),
            _verdict("passive_screen_check", not any(e.screen_pattern for e in envs), m.SCREEN_PATTERN),
        ]

    def faces(
        self, frames: Sequence[FrameObservation], times: Sequence[int], reference_ref: bool, spoken: bool = False,
    ) -> list[CalibrationCheck]:
        """One face in every frame, face and mouth uncovered, and the enrolled identity."""
        single = all(f.face_count == 1 for f in frames)
        judged = sum(1 for f in frames if f.occlusion is not None and f.occlusion.measured)

        def covered(pick: Callable[[Any], bool]) -> bool:
            flags = [FlagSample(at, pick(f.occlusion) if f.occlusion is not None and f.occlusion.measured else None)
                     for f, at in zip(frames, times)]
            return longest(RunTracker().evaluate("occlusion", None, None, flags)) >= t.OCC_MIN_RUN_MS

        checks = [_verdict("single_face", single, m.VOICE_SINGLE_FACE if spoken else m.SINGLE_FACE)]
        if not single:
            return checks
        face_covered = covered(lambda o: o.face)
        checks.append(_verdict("face_uncovered", not face_covered, m.FACE_COVERED))
        checks.append(_verdict("mouth_uncovered", not covered(lambda o: o.mouth or o.face), m.MOUTH_COVERED))
        if not spoken:
            checks.append(_verdict(
                "occlusion_reference", reference_ref and judged >= t.CAL_MIN_OCCLUSION_JUDGED, m.OCCLUSION_UNJUDGED))
        return checks

    def identity(self, frames: Sequence[FrameObservation], spoken: bool = False) -> CalibrationCheck:
        """The enrolled face matches in every given frame; a frame with no verdict is never a pass."""
        if any(f.identity_match is None for f in frames):
            return _fail("identity", m.VOICE_IDENTITY if spoken else m.IDENTITY_UNKNOWN)
        return _verdict("identity", all(f.identity_match for f in frames), m.VOICE_IDENTITY if spoken else m.IDENTITY)

    def movement(self, frames: Sequence[FrameObservation], action: str) -> list[CalibrationCheck]:
        """Frontal start and end (pose and gaze) and the requested turn, from the 3D pose only."""
        if not all(f.pose_3d for f in frames):
            return [_fail("liveness", m.POSE_3D_UNAVAILABLE, 503)]
        k = max(1, min(3, len(frames) // 3))
        head, tail, middle = frames[:k], frames[-k:], frames[k:-k]
        usable = [f for f in (*head, *tail) if not f.blink]
        frontal = bool(usable) and all(
            f.yaw_deg is not None and abs(f.yaw_deg) <= t.CAL_FRONTAL_MAX_YAW_DEG
            and classify(sample_from_frame(f, 0), DEFAULT_ZONE) == IN
            for f in usable)
        start = statistics.median(float(f.yaw_deg or 0.0) for f in head)
        end = statistics.median(float(f.yaw_deg or 0.0) for f in tail)
        returned = abs(end - start) <= t.CAL_RETURN_MAX_YAW_DELTA_DEG
        direction = -1 if action == "TURN_LEFT" else 1
        turned = sum(1 for f in middle if f.yaw_deg is not None
                     and direction * (float(f.yaw_deg) - start) >= t.CAL_TURN_MIN_YAW_DELTA_DEG)
        return [
            _verdict("frontal", frontal and returned, m.FRONTAL),
            _verdict("liveness", bool(middle) and turned >= min(t.CAL_TURN_MIN_FRAMES, len(middle)), m.LIVENESS),
        ]

    # ---- the audio steps ------------------------------------------------------------------------

    def ambient(self, quiet: AudioObservation, segment: np.ndarray) -> list[CalibrationCheck]:
        """The silence segment: no speech (VAD) and a low ambient floor."""
        if quiet.vad_unavailable:
            return [_fail("background_quiet", m.VAD_UNAVAILABLE, 503)]
        voiced, run = run_stats(quiet.voiced_flags)
        if voiced >= t.CAL_AMBIENT_MAX_VOICED_CHUNKS or run >= t.CAL_AMBIENT_MAX_RUN_CHUNKS:
            return [_fail("background_quiet", m.SPEECH_DURING_SILENCE)]
        return [_verdict("background_quiet", signal_rms(segment) <= t.CAL_AMBIENT_MAX_RMS, m.BACKGROUND_NOISE)]

    def speech(self, measured: AudioObservation, phrase: np.ndarray) -> list[CalibrationCheck]:
        """The speech segment: enough voiced speech, one voice and a silent final pause."""
        if measured.vad_unavailable:
            return [_fail("microphone", m.VAD_UNAVAILABLE, 503)]
        voiced, run = run_stats(measured.voiced_flags)
        loud_enough = (voiced >= t.CAL_SPEECH_MIN_VOICED_CHUNKS and run >= t.CAL_SPEECH_MIN_RUN_CHUNKS
                       and signal_rms(phrase) >= t.CAL_SPEECH_MIN_RMS)
        if not loud_enough:
            return [_fail("microphone", m.NOT_ENOUGH_SPEECH)]
        pause_from = int(t.CAL_PAUSE_FROM_S * t.AUDIO_SAMPLE_RATE / t.VAD_CHUNK_SAMPLES)
        pause_voiced, pause_run = run_stats(measured.voiced_flags[pause_from:])
        checks = [_ok("microphone"), _verdict(
            "speech_pause", pause_voiced < t.CAL_AMBIENT_MAX_VOICED_CHUNKS and pause_run < t.CAL_AMBIENT_MAX_RUN_CHUNKS,
            m.SPEECH_DURING_PAUSE)]
        if measured.speaker_model_unavailable:
            return [*checks, _fail("single_speaker", m.SPEAKER_MODELS_UNAVAILABLE, 503)]
        if measured.overlap_s >= t.SPEAKER_OVERLAP_MIN_S:
            return [*checks, _fail("no_overlap", m.OVERLAPPING_VOICES)]
        if measured.speakers > 1:
            return [*checks, _fail("single_speaker", m.MORE_THAN_ONE_VOICE)]
        confirmed = measured.diarized and measured.speakers == 1
        return [*checks, _verdict("single_speaker", confirmed, m.SINGLE_VOICE_UNCONFIRMED), _ok("no_overlap")]


class _Checks:
    """The checks collected so far; a failed one raises, a repeated name is the AND of its results."""

    def __init__(self) -> None:
        self.results: dict[str, bool] = {}

    def add(self, checks: Sequence[CalibrationCheck]) -> None:
        for check in checks:
            if not check.passed:
                raise CalibrationRejected(check.name, check.reason, check.status)
            self.results[check.name] = self.results.get(check.name, True) and check.passed


class CalibrationEngine:
    """Measures a calibration's evidence with the shared analyzers and judges it with a ``CalibrationProfile``."""

    def __init__(
        self,
        frames: FrameAnalyzer,
        audio: AudioAnalyzer,
        extractor: vp.EmbeddingExtractor,
        profile: Optional[CalibrationProfile] = None,
        state: Optional[SessionStateStore] = None,
    ) -> None:
        self.frames, self.audio, self.extractor = frames, audio, extractor
        self.profile = profile or CalibrationProfile()
        self.state = state if state is not None else frames.state

    @classmethod
    def create(
        cls,
        state: Optional[SessionStateStore] = None,
        vision_provider: Optional[Callable[[], tuple[Any, Any]]] = None,
        landmarker_provider: Optional[Callable[[], Any]] = None,
        speaker_segments: Optional[Callable[[np.ndarray], Any]] = None,
        extractor: Optional[vp.EmbeddingExtractor] = None,
    ) -> "CalibrationEngine":
        """Wires the default analyzers for one calibration: per-request state, the process-wide landmarker."""
        store = state if state is not None else InMemoryStateStore()
        extractor = extractor or vp.default_extractor()
        loaded: list[tuple[Any, Any]] = []

        def models() -> tuple[Any, Any]:
            """The YuNet/SFace pair is created once per calibration, not once per step."""
            if not loaded:
                loaded.append((vision_provider or create_vision_models)())
            return loaded[0]

        return cls(
            FrameAnalyzer(store, vision_provider=models,
                          landmarker_provider=landmarker_provider, identity_any_pose=True),
            AudioAnalyzer(store, speaker_segments=speaker_segments, extractor=extractor, vad_floor=0.0,
                          min_speaker_s=t.CAL_SPEAKER_MIN_DURATION_S),
            extractor,
        )

    def assess(self, evidence: CalibrationEvidence) -> CalibrationOutput:
        """Runs every step in order and raises ``CalibrationRejected`` at the first failing check."""
        if not self.frames.identity_models_ready():
            raise CalibrationRejected("models", m.VISION_UNAVAILABLE, 503)
        session = f"calibration:{uuid.uuid4()}"
        checks = _Checks()
        self._movement(evidence, session, checks)
        reference_ref = self.state.get_track(session, "occlusion_ref")
        zone = self._gaze(evidence, checks) if evidence.complete else None
        voiceprint = self._voice(evidence, session, checks)
        required = REQUIRED_CHECKS if evidence.complete else REQUIRED_CHECKS - NEW_CONTRACT_CHECKS
        if set(checks.results) != required or not all(checks.results.values()) or reference_ref is None:
            raise CalibrationRejected("incomplete", m.INCOMPLETE)
        return CalibrationOutput(dict(checks.results), zone, voiceprint, dict(reference_ref))

    # ---- movement ---------------------------------------------------------------------------------

    def _measure(
        self, frames: Sequence[str], reference: Optional[np.ndarray], session: Optional[str],
        times: Optional[Sequence[int]] = None,
    ) -> FrameBatch:
        batch = self.frames.analyze_frames(frames, reference, session, times_ms=times)
        if batch.model_unavailable or len(batch.frames) != len(frames):
            raise CalibrationRejected("models", m.VISION_UNAVAILABLE, 503)
        return batch

    @staticmethod
    def _decode(frames: Sequence[str]) -> list[np.ndarray]:
        images = []
        for raw in frames:
            image = decode_frame(raw)
            if image is None:
                raise CalibrationRejected("frames", m.INVALID_IMAGE)
            if not environment.size_acceptable((image.shape[1], image.shape[0])):
                raise CalibrationRejected("frames", m.IMAGE_SIZE)
            images.append(image)
        return images

    def _movement(self, evidence: CalibrationEvidence, session: str, checks: _Checks) -> None:
        frames = list(evidence.frames)
        images = self._decode(frames)
        digests = len({hashlib.sha256(raw.split(",", 1)[-1].encode()).digest() for raw in frames})
        times = [i * t.CAL_MOVEMENT_FRAME_GAP_MS for i in range(len(frames))]
        batch = self._measure(frames, evidence.reference, session, times)
        observed = batch.frames
        envs = [environment.measure(image, f.face_box) for image, f in zip(images, observed)]
        reference_ref = (self.state.get_track(session, "occlusion_ref") or {}).get("n", 0) >= t.OCC_REF_MIN_SAMPLES
        checks.add(self.profile.camera(
            observed, digests, environment.virtual_camera_label(evidence.camera_label), envs, times))
        checks.add(self.profile.faces(observed, times, reference_ref))
        checks.add([self.profile.identity(observed)])
        checks.add(self.profile.movement(observed, evidence.action))

    # ---- gaze zone --------------------------------------------------------------------------------

    def _gaze(self, evidence: CalibrationEvidence, checks: _Checks) -> GazeZone:
        per_target: dict[str, FrameBatch] = {}
        for name in TARGETS:
            target_frames = list((evidence.gaze_points or {}).get(name, ()))
            if not target_frames:
                raise CalibrationRejected("gaze_zone", m.GAZE_CALIBRATION_ERRORS["FACE_MISSING"][1])
            per_target[name] = self._measure(
                target_frames, evidence.reference if name == "CENTER" else None, None)
        center = [f for f in per_target["CENTER"].frames if f.identity_match]
        if len(center) < min(t.CAL_MIN_IDENTITY_CENTER_FRAMES, len(per_target["CENTER"].frames)) or not center:
            raise CalibrationRejected("identity", m.IDENTITY)
        try:
            zone = compute_zone(per_target)
        except GazeCalibrationError as error:
            status, message = m.GAZE_CALIBRATION_ERRORS[error.code]
            raise CalibrationRejected("gaze_zone", message, status) from error
        checks.add([_ok("gaze_zone")])
        return zone

    # ---- voice ------------------------------------------------------------------------------------

    @staticmethod
    def _timeline_ok(times: Sequence[int], ambient_ms: int, duration_ms: int) -> bool:
        """The spoken frames must be ordered, cover the speech segment and have no large gaps."""
        if not t.CAL_VOICE_FRAME_MIN <= len(times) <= t.CAL_VOICE_FRAME_MAX:
            return False
        gaps = np.diff(np.asarray(times, dtype=np.float64))
        return bool(
            times[0] >= 0 and times[0] <= ambient_ms + t.CAL_VOICE_FRAME_FIRST_SLACK_MS
            and times[-1] >= duration_ms - t.CAL_VOICE_FRAME_LAST_SLACK_MS and times[-1] <= duration_ms + 100
            and np.all(gaps > t.CAL_VOICE_FRAME_MIN_GAP_MS) and np.max(gaps) <= t.CAL_VOICE_FRAME_MAX_GAP_MS
            and np.median(gaps) <= t.CAL_VOICE_FRAME_MEDIAN_GAP_MAX_MS)

    def _voice(self, evidence: CalibrationEvidence, session: str, checks: _Checks) -> Optional[dict[str, Any]]:
        samples = np.asarray(evidence.audio, dtype=np.float32)
        ambient_ms = evidence.ambient_ms
        duration_ms = samples.size * 1000 // t.AUDIO_SAMPLE_RATE
        speech_s = (duration_ms - ambient_ms) / 1000.0
        if (samples.ndim != 1 or not np.isfinite(samples).all() or np.any(np.abs(samples) > 1)
                or ambient_ms < t.CAL_AMBIENT_MIN_MS or not t.CAL_SPEECH_MIN_S <= speech_s <= t.CAL_SPEECH_MAX_S
                or duration_ms > t.CAL_RECORDING_MAX_S * 1000):
            raise CalibrationRejected("audio", m.AUDIO_SIZE)
        times = [int(at) for at, _ in evidence.voice_frames]
        if not self._timeline_ok(times, ambient_ms, duration_ms):
            raise CalibrationRejected("frames", m.VOICE_VIDEO)

        profile = self.profile

        class Rules:
            def ambient(self, quiet: AudioObservation, segment: np.ndarray) -> None:
                checks.add(profile.ambient(quiet, segment))

            def speech(self, measured: AudioObservation, phrase: np.ndarray, voiced: np.ndarray) -> None:
                checks.add(profile.speech(measured, phrase))

        try:
            recording = enrollment.measure_recording(samples, ambient_ms, self.audio, Rules())
        except enrollment.EnrollmentError as error:
            raise self._enrollment_rejected(error) from error
        except vp.SpeakerModelUnavailable as error:
            raise CalibrationRejected("single_speaker", m.SPEAKER_MODELS_UNAVAILABLE, 503) from error

        voice_images = [raw for _, raw in evidence.voice_frames]
        if any(image.shape[1] > t.CAL_VOICE_FRAME_MAX_WIDTH for image in self._decode(voice_images)):
            raise CalibrationRejected("frames", m.VOICE_VIDEO)
        batch = self._measure(voice_images, None, session, times)
        observed = batch.frames
        checks.add(self.profile.faces(observed, times, True, spoken=True))
        sample_at = sorted({0, len(observed) // 2, len(observed) - 1})
        identity = self._measure([voice_images[i] for i in sample_at], evidence.reference, None)
        checks.add([self.profile.identity(identity.frames, spoken=True)])
        server_mouth = [(at, sample.mouth_open) for f, at in zip(observed, times)
                        for sample in [sample_from_frame(f, at)] if f.face_count == 1 and sample.mouth_open is not None]
        try:
            if not evidence.complete:
                # No browser telemetry in this contract: the voice must follow the mouth the server measured itself.
                enrollment.judge_sync(recording, ambient_ms, None, server_mouth)
                checks.add([_ok("mouth_audio_sync")])
                return None
            record = enrollment.finish_enrollment(recording, ambient_ms, evidence.mouth, server_mouth, self.extractor)
        except enrollment.EnrollmentError as error:
            raise self._enrollment_rejected(error) from error
        except vp.SpeakerModelUnavailable as error:
            raise CalibrationRejected("voiceprint", m.SPEAKER_MODELS_UNAVAILABLE, 503) from error
        checks.add([_ok("mouth_telemetry"), _ok("mouth_audio_sync"), _ok("voiceprint")])
        return record

    @staticmethod
    def _enrollment_rejected(error: enrollment.EnrollmentError) -> CalibrationRejected:
        """Maps an enrollment code to the calibration check it belongs to and the message shown for it."""
        status, message = m.VOICE_CALIBRATION_ERRORS.get(error.code, (400, m.INCOMPLETE))
        check = {"UNTRUSTED_TELEMETRY": "mouth_telemetry", "UNSYNCED": "mouth_audio_sync", "NO_MOUTH": "mouth_audio_sync",
                 "INCONSISTENT": "voiceprint", "INSUFFICIENT_SPEECH": "microphone", "MULTIPLE_SPEAKERS": "single_speaker",
                 "AMBIENT_NOT_QUIET": "background_quiet"}.get(error.code, "voiceprint")
        if error.code == "UNSYNCED":
            message = m.VOICE_WITHOUT_MOUTH  # the wording the pre-exam calibration has always used
        return CalibrationRejected(check, message, status)
