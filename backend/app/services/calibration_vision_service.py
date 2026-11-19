"""Pre-exam calibration entry point: a thin adapter over the integrity engine (T9 / S9).

Every check runs in ``app.services.integrity.calibration`` on the same analyzers and thresholds as supervision; this
module only maps the pre-exam request (``CalibrationVerifyRequest``) onto the engine's evidence and the engine's
verdict onto the check names ``EvaluationCalibrationService`` stores. Strict local calibration: texture and motion
heuristics are not a validated presentation-attack detector.
"""
from typing import Any, Optional, Sequence

import numpy as np

from app.core.exceptions import SkillMatchException
from app.services.integrity import messages as m, thresholds as t
from app.services.integrity.calibration import CalibrationEngine, CalibrationEvidence, CalibrationRejected
from app.services.integrity.frame_analyzer import parse_reference_embedding

# The checks the pre-exam gate has always stored (the engine's extra checks are enforced but not stored here).
STORED_CHECKS = ("lighting", "framing", "single_face", "microphone", "background_quiet", "identity", "liveness",
                 "passive_screen_check", "single_speaker", "no_overlap", "mouth_audio_sync", "speech_pause")

BIOMETRIC_INVALID = "Tu referencia biométrica no es válida. Volvé a registrar tu rostro."


def reject(message: str, status: int = 400) -> None:
    raise SkillMatchException(statuscode=status, message=message)


class CalibrationVisionService:
    @staticmethod
    def engine() -> CalibrationEngine:
        """A fresh engine per request (per-request state, the process-wide landmarker); tests replace this seam."""
        return CalibrationEngine.create()

    @staticmethod
    def reference(enrollment: Optional[str]) -> np.ndarray:
        """The enrolled face as a unit vector; anything malformed is rejected (never a fallback)."""
        unit = parse_reference_embedding(enrollment)
        if unit is None:
            reject(BIOMETRIC_INVALID)
        return unit

    @staticmethod
    def audio_valid(samples: Sequence[float], minimum: int, maximum: int) -> bool:
        audio = np.asarray(samples, dtype=np.float32)
        return bool(audio.ndim == 1 and minimum <= audio.size <= maximum and np.isfinite(audio).all()
                    and not np.any(np.abs(audio) > 1))

    @classmethod
    def assess(cls, frames: Sequence[str], audio_samples: Sequence[float], camera_label: str, action: str,
               enrollment: Optional[str], ambient_audio_samples: Optional[Sequence[float]] = None,
               spoken_frames: Optional[Sequence[Any]] = None) -> dict[str, bool]:
        """The pre-exam verdict: {check: True} for every stored check, or a SkillMatchException (400, or 503 when a
        model is missing). The engine's additional checks (camera, covered face or mouth, frontal pose, occlusion
        reference) are enforced by raising; they are not part of the stored set."""
        reference = cls.reference(enrollment)
        ambient = ambient_audio_samples or []
        if not (cls.audio_valid(ambient, 32000, 64000) and cls.audio_valid(audio_samples, 112000, 160000)):
            reject(m.AUDIO_SIZE)
        ambient_ms = len(ambient) * 1000 // t.AUDIO_SAMPLE_RATE
        evidence = CalibrationEvidence(
            action=action, frames=list(frames), gaze_points=None,
            audio=[*ambient, *audio_samples], ambient_ms=ambient_ms,
            voice_frames=[(int(round(frame.time_ms)) + ambient_ms, frame.image) for frame in spoken_frames or []],
            mouth=None, reference=reference, camera_label=camera_label,
        )
        try:
            output = cls.engine().assess(evidence)
        except CalibrationRejected as error:
            reject(error.message, error.status)
        return {name: bool(output.checks.get(name)) for name in STORED_CHECKS}
