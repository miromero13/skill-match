"""Continuous audiovisual window analysis for trial supervision (backward-compatible facade).

The analysis itself lives in the shared integrity engine (``app.services.integrity``): MediaPipe
FaceLandmarker pose/blendshapes, OpenCV YuNet + SFace identity, WebRTC VAD and Sherpa-ONNX diarization,
all local (zero third-party cloud APIs). This class keeps the public methods the supervision API and the
tests have always used and delegates each of them to the engine's analyzers.

The class-level state (``_trial_baselines``, ``_trial_audio_state``, ``_state_lock``) and the overridable
model hooks (``get_vision_models``, ``get_mediapipe_landmarker``, ``_analyze_with_mediapipe``) stay here so
they remain the seams existing callers and tests patch; the engine is wired over them on every call.
"""
import threading
from collections import OrderedDict
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from app.services.integrity import frame_analyzer as frames
from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity import enrollment
from app.services.integrity.engine import IntegrityEngine
from app.services.integrity.frame_analyzer import FrameAnalyzer, LandmarkerLifecycle
from app.services.integrity.models import FrameBatch, FrameObservation, GazeSample, GazeZone, MouthPatch
from app.services.integrity.policy import SupervisionProfile
from app.services.integrity.state import InMemoryStateStore
from app.services.integrity.sync_analyzer import SyncAnalyzer
from app.services.integrity.thresholds import (  # noqa: F401  (re-exported for existing importers)
    AUDIO_LENGTH_TOLERANCE,
    AUDIO_SAMPLE_RATE,
    MAX_FRAME_HEIGHT,
    MAX_FRAME_WIDTH,
)


class ContinuousSupervisionService(LandmarkerLifecycle):
    # Bounded in-memory per-trial neutral 3D pose baselines (max 256 active trials)
    _trial_baselines: OrderedDict[str, dict[str, float]] = OrderedDict()
    # Bounded in-memory rolling 2.4s audio buffer & speaker state per trial
    _trial_audio_state: OrderedDict[str, dict[str, Any]] = OrderedDict()
    # Bounded in-memory out-of-zone gaze run still open at the end of each trial's last window
    _trial_gaze_runs: OrderedDict[str, dict[str, Any]] = OrderedDict()
    # Bounded in-memory named records per trial: confirmation runs/streaks and the occlusion reference (T7)
    _trial_tracks: OrderedDict[str, dict[str, Any]] = OrderedDict()
    # Inference runs on worker threads: the per-trial dictionaries are mutated concurrently.
    _state_lock = threading.RLock()
    # The landmarker is a shared native object; its detect() lock lives with the frame analyzer.
    _mp_detect_lock = frames.MP_DETECT_LOCK

    # ---- wiring ---------------------------------------------------------------------------------

    @classmethod
    def _store(cls) -> InMemoryStateStore:
        return InMemoryStateStore(
            cls._trial_baselines, cls._trial_audio_state, cls._state_lock, gaze_runs=cls._trial_gaze_runs,
            tracks=cls._trial_tracks,
        )

    @classmethod
    def _frame_analyzer(cls, use_mediapipe: bool = True) -> FrameAnalyzer:
        return FrameAnalyzer(
            cls._store(),
            vision_provider=cls.get_vision_models,
            landmarker_provider=cls.get_mediapipe_landmarker if use_mediapipe else (lambda: None),
            mediapipe_runner=cls._analyze_with_mediapipe,
        )

    @classmethod
    def _audio_analyzer(cls) -> AudioAnalyzer:
        return AudioAnalyzer(cls._store())

    # ---- frame analysis -------------------------------------------------------------------------

    @staticmethod
    def get_vision_models():
        """Creates per-request YuNet detector and SFace recognizer instances."""
        return frames.create_vision_models()

    @staticmethod
    def decode_frame(raw: str) -> Optional[np.ndarray]:
        """Safely decodes a base64 JPEG; oversized or malformed images are rejected before pixel decoding."""
        return frames.decode_frame(raw)

    @classmethod
    def _get_or_update_baseline(
        cls,
        trial_key: Optional[str],
        metrics: dict[str, float],
        is_frontal_candidate: bool,
    ) -> Optional[dict[str, float]]:
        return cls._store().update_baseline(trial_key, metrics, is_frontal_candidate)

    @classmethod
    def _analyze_with_mediapipe(
        cls,
        image_bgr: np.ndarray,
        trial_key: Optional[str],
        landmarker: Any,
    ) -> Optional[FrameObservation]:
        """Runs the injected MediaPipe landmarker; returns the engine's ``FrameObservation`` (or None)."""
        return cls._frame_analyzer().analyze_mediapipe(image_bgr, trial_key, landmarker)

    @classmethod
    def analyze_frame_face(
        cls,
        image: np.ndarray,
        detector: Any,
        recognizer: Any,
        reference_embedding: Optional[np.ndarray],
        trial_key: Optional[str] = None,
        landmarker: Any = None,
    ) -> dict[str, Any]:
        """Analyzes one frame with the injected models (MediaPipe optional, YuNet, SFace).

        When no model produced a result the frame is flagged ``model_unavailable`` and never reported
        as a clean face (fail closed).
        """
        return cls._frame_analyzer().analyze_frame(
            image, detector, recognizer, reference_embedding, session_key=trial_key, landmarker=landmarker
        ).to_legacy_dict()

    @classmethod
    def analyze_gaze_targets(cls, frames_by_target: Mapping[str, Sequence[str]]) -> dict[str, FrameBatch]:
        """Measures the calibration frames of each screen target (no per-trial baseline is touched)."""
        analyzer = cls._frame_analyzer()
        return {name: analyzer.analyze_frames(frames, None, None) for name, frames in frames_by_target.items()}

    @classmethod
    def compute_mouth_trace(cls, patches: list[Optional[MouthPatch]]) -> tuple[bool, list[float]]:
        """Inter-frame cheek-compensated mouth movements (fallback for patch-based tests)."""
        return SyncAnalyzer.compute_mouth_trace(patches)

    @classmethod
    def compute_mouth_movement(cls, patches: list[Optional[MouthPatch]]) -> bool:
        moving, _ = cls.compute_mouth_trace(patches)
        return moving

    # ---- audio analysis -------------------------------------------------------------------------

    @classmethod
    def _detect_multi_speaker_or_background_media(
        cls,
        audio: np.ndarray,
        voiced_flags: list[bool],
        trial_key: Optional[str],
    ) -> bool:
        """Detects multiple speakers or overlapping voices using Sherpa-ONNX Pyannote diarization."""
        return cls._audio_analyzer().detect_multiple_speakers(audio, voiced_flags, trial_key)

    @classmethod
    def analyze_audio(
        cls,
        samples: Optional[list[float]],
        trial_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyzes 16kHz audio samples using strict WebRTC VAD(3) and CalibrationSpeakerService."""
        return cls._audio_analyzer().analyze(samples, trial_key).to_legacy_dict()

    @staticmethod
    def _audio_missing(samples: Optional[list[float]], duration_ms: Optional[int]) -> bool:
        return AudioAnalyzer.is_missing(samples, duration_ms)

    @staticmethod
    def enroll_voice(audio: Sequence[float], ambient_ms: int, mouth: Sequence[tuple[int, float]]) -> dict[str, Any]:
        """The voiceprint record of a calibration recording (raises ``EnrollmentError`` / ``SpeakerModelUnavailable``)."""
        return enrollment.enroll_voice(audio, ambient_ms, mouth)

    # ---- window ---------------------------------------------------------------------------------

    @classmethod
    def assess_window(
        cls,
        frames_b64: list[str],
        audio_samples: Optional[list[float]],
        mode: str = "UNIFIED",
        biometric_embedding_json: Optional[str] = None,
        trial_id: Optional[str] = None,
        use_mediapipe: bool = True,
        duration_ms: Optional[int] = None,
        gaze_zone: Optional[Mapping[str, float]] = None,
        frame_times_ms: Optional[Sequence[int]] = None,
        gaze_samples: Sequence[Any] = (),
        observed_at_ms: Optional[int] = None,
        voiceprint: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluates an audiovisual supervision window and determines anomalies.

        ``gaze_zone`` is the trial's calibrated screen zone (None: conservative defaults), ``frame_times_ms``
        the capture offset of each frame from the window start (``observed_at_ms``, epoch ms) and
        ``gaze_samples`` the browser's ~15 fps readings, which the server only trusts when they agree with
        its own measurement of the frames (S5 / S12). ``voiceprint`` is the trial's enrolled voiceprint record
        (None: speech is reported as unverified, S3 / S11).

        Fails closed: when no vision model is usable the window reports ``MODEL_UNAVAILABLE`` with
        ``face_count`` 0 and no identity verdict instead of a clean face. Missing evidence is never clean
        either: no decodable frame reports ``VIDEO_MISSING`` and absent or length-inconsistent audio
        (checked against ``duration_ms`` at 16 kHz when given) reports ``AUDIO_MISSING``.
        """
        engine = IntegrityEngine(cls._frame_analyzer(use_mediapipe), cls._audio_analyzer())
        assessment = engine.assess_window(
            frames_b64,
            audio_samples,
            duration_ms=duration_ms,
            reference_embedding=frames.parse_reference_embedding(biometric_embedding_json),
            session_key=trial_id,
            profile=SupervisionProfile(gaze_runs=cls._store()),
            gaze_zone=GazeZone.from_dict(gaze_zone) if gaze_zone else None,
            frame_times_ms=frame_times_ms,
            gaze_samples=[
                GazeSample(
                    t_ms=sample.t_ms, face_count=sample.face_count, head_pitch=sample.head_pitch,
                    head_yaw=sample.head_yaw, gaze_h=sample.gaze_h, gaze_v=sample.gaze_v, blink=sample.blink,
                    mouth_open=getattr(sample, "mouth_open", None),
                )
                for sample in gaze_samples
            ],
            window_start_ms=observed_at_ms,
            voiceprint=voiceprint,
        )
        return assessment.to_dict()
