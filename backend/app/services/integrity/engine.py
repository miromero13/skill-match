"""The shared integrity engine: analyzers measure, a profile judges.

``IntegrityEngine.assess_window`` runs the frame, audio and sync analyzers over one audiovisual window and
hands the resulting ``WindowObservation`` to a policy profile (``SupervisionProfile`` for exams,
``CalibrationProfile`` for calibration, T9). Supervision (``ContinuousSupervisionService``) is a thin facade
over this class.

Calibration reuse map (T9 migrates these services; nothing here depends on them except diarization):
    CalibrationVisionService   -> FrameAnalyzer.analyze_frame  (pose, face count, identity)
    CalibrationAudioService    -> AudioAnalyzer.analyze        (RMS, VAD speech, noise)
    CalibrationSpeakerService  -> AudioAnalyzer.detect_multiple_speakers (diarization via .segments)
    CalibrationAVService       -> sync_analyzer.voice_mouth_coexistence / SyncAnalyzer.mouth_movement
"""
from typing import Any, Callable, Optional, Sequence

import numpy as np

from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.frame_analyzer import FrameAnalyzer
from app.services.integrity.gaze import check_telemetry, normalize_frame_times, sample_from_frame
from app.services.integrity.models import GazeEvidence, GazeSample, GazeZone, WindowAssessment, WindowObservation
from app.services.integrity.policy import PolicyProfile, SupervisionProfile
from app.services.integrity.state import InMemoryStateStore, SessionStateStore
from app.services.integrity.sync_analyzer import SyncAnalyzer


class IntegrityEngine:
    def __init__(
        self,
        frame_analyzer: FrameAnalyzer,
        audio_analyzer: AudioAnalyzer,
        sync_analyzer: Optional[SyncAnalyzer] = None,
    ) -> None:
        self.frames = frame_analyzer
        self.audio = audio_analyzer
        self.sync = sync_analyzer or SyncAnalyzer()

    @classmethod
    def create(
        cls,
        state: Optional[SessionStateStore] = None,
        vision_provider: Optional[Callable[[], tuple[Any, Any]]] = None,
        landmarker_provider: Optional[Callable[[], Any]] = None,
    ) -> "IntegrityEngine":
        """Wires the default analyzers over one state store (in-memory unless another one is given)."""
        store = state if state is not None else InMemoryStateStore()
        return cls(
            FrameAnalyzer(store, vision_provider=vision_provider, landmarker_provider=landmarker_provider),
            AudioAnalyzer(store),
        )

    def observe_window(
        self,
        frames: Sequence[str],
        audio: Optional[Sequence[float]],
        duration_ms: Optional[int] = None,
        reference_embedding: Optional[np.ndarray] = None,
        session_key: Optional[str] = None,
        gaze_zone: Optional[GazeZone] = None,
        frame_times_ms: Optional[Sequence[int]] = None,
        gaze_samples: Sequence[GazeSample] = (),
        window_start_ms: Optional[int] = None,
    ) -> WindowObservation:
        """Measures a window: ``frames`` are base64 JPEGs, ``audio`` 16 kHz mono samples in [-1, 1].

        ``frame_times_ms`` are the frames' capture offsets from the window start and ``gaze_samples`` the
        browser's own ~15 fps readings (S12): the server measurement is authoritative, so the telemetry is
        only kept when it agrees with the server's frames and contradicting telemetry is flagged.
        """
        times = normalize_frame_times(frame_times_ms, len(frames), duration_ms)
        batch = self.frames.analyze_frames(frames, reference_embedding, session_key, times_ms=times)
        server = tuple(sample_from_frame(f, at) for f, at in zip(batch.frames, batch.times_ms))
        check = check_telemetry(server, gaze_samples)
        evidence = GazeEvidence(
            server=server, client=tuple(gaze_samples) if check.trusted else (), client_mismatch=check.mismatch,
            window_start_ms=window_start_ms, zone=gaze_zone, session_key=session_key,
        )
        mouth_moving, movements = self.sync.mouth_movement(batch.frames) if batch.frames else (False, [])
        audio_missing = self.audio.is_missing(audio, duration_ms)
        return WindowObservation(
            frames=batch.frames,
            video_missing=batch.video_missing,
            model_unavailable=batch.model_unavailable,
            audio=self.audio.analyze(audio, session_key),
            audio_missing=audio_missing,
            mouth_moving=mouth_moving,
            mouth_movements=tuple(movements),
            duration_ms=duration_ms,
            gaze=evidence,
            frame_times_ms=batch.times_ms,
        )

    def assess_window(
        self,
        frames: Sequence[str],
        audio: Optional[Sequence[float]],
        duration_ms: Optional[int] = None,
        reference_embedding: Optional[np.ndarray] = None,
        session_key: Optional[str] = None,
        profile: Optional[PolicyProfile] = None,
        gaze_zone: Optional[GazeZone] = None,
        frame_times_ms: Optional[Sequence[int]] = None,
        gaze_samples: Sequence[GazeSample] = (),
        window_start_ms: Optional[int] = None,
    ) -> WindowAssessment:
        """Measures a window and judges it with ``profile`` (default: ``SupervisionProfile``).

        Fails closed: no usable vision model reports MODEL_UNAVAILABLE with face_count 0 and no identity
        verdict; no decodable frame reports VIDEO_MISSING; absent or length-inconsistent audio (against
        ``duration_ms`` at 16 kHz) reports AUDIO_MISSING.
        """
        observation = self.observe_window(
            frames, audio, duration_ms, reference_embedding, session_key,
            gaze_zone=gaze_zone, frame_times_ms=frame_times_ms, gaze_samples=gaze_samples,
            window_start_ms=window_start_ms,
        )
        return (profile or SupervisionProfile()).evaluate(observation)
