"""Pre-exam calibration entry point: a thin adapter over the integrity engine (T9 / S9).

Every check runs in ``app.services.integrity.calibration`` on the same analyzers and thresholds as supervision; this
module only maps the pre-exam request (``CalibrationVerifyRequest``) onto the engine's evidence; the verdict, with
the zone, voiceprint and occlusion reference, goes to ``EvaluationCalibrationService`` to be stored. Strict local calibration: texture and motion
heuristics are not a validated presentation-attack detector.
"""
from typing import Any, Optional, Sequence

import numpy as np

from app.core.exceptions import SkillMatchException
from app.services.integrity import messages as m, thresholds as t
from app.services.integrity.calibration import (
    CalibrationEngine, CalibrationEvidence, CalibrationOutput, CalibrationRejected,
)
from app.services.integrity.frame_analyzer import parse_reference_embedding

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
    def assess(cls, payload: Any, action: str, enrollment: Optional[str]) -> CalibrationOutput:
        """Runs the whole calibration on the engine: a ``CalibrationOutput`` (every required check passed, plus the
        gaze zone, voiceprint and occlusion reference supervision needs) or a SkillMatchException (400, or 503 when a
        model is missing: no voiceprint without the speaker model, never a pass)."""
        reference = cls.reference(enrollment)
        ambient = payload.ambient_audio_samples
        if not (cls.audio_valid(ambient, 32000, 64000) and cls.audio_valid(payload.audio_samples, 112000, 160000)):
            reject(m.AUDIO_SIZE)
        ambient_ms = len(ambient) * 1000 // t.AUDIO_SAMPLE_RATE
        evidence = CalibrationEvidence(
            action=action, frames=list(payload.frames),
            gaze_points={point.target: list(point.frames) for point in payload.gaze_points},
            audio=[*ambient, *payload.audio_samples], ambient_ms=ambient_ms,
            voice_frames=[(int(round(frame.time_ms)) + ambient_ms, frame.image) for frame in payload.spoken_frames],
            mouth=[(sample.t_ms + ambient_ms, sample.mouth_open) for sample in payload.mouth_samples],
            reference=reference, camera_label=payload.camera_label,
        )
        try:
            return cls.engine().assess(evidence)
        except CalibrationRejected as error:
            reject(error.message, error.status)
