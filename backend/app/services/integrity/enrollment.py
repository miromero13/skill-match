"""Voice calibration: turns a recorded control phrase into the trial's voiceprint (S3, S4, S11).

The recording is a short silence segment (the ambient floor, later used for BACKGROUND_AUDIO) followed by the
candidate reading a phrase aloud, with the mouth-aperture readings captured meanwhile. The same analyzers that
supervise the exam judge it, as guided checks that must pass:

  * the silence segment has neither speech nor loud noise;
  * enough voiced speech (>= 3 s) and one voice only (diarization: no several speakers, no overlap);
  * the voice follows the mouth (lip-sync correlation), so a played recording cannot be enrolled;
  * the voice segments are mutually consistent (``voiceprint.enroll``).

Failures raise ``EnrollmentError`` (``code`` says why); a missing or unusable speaker model raises
``voiceprint.SpeakerModelUnavailable``: calibration fails closed, there is no unverified enrollment.
"""
from typing import Any, Optional, Sequence

import numpy as np

from app.services.integrity import lipsync, thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.audio_analyzer import AudioAnalyzer, voiced_audio
from app.services.integrity.state import InMemoryStateStore
from app.services.integrity.voiceprint import EnrollmentError

__all__ = ["EnrollmentError", "InMemoryStateStore", "enroll_voice"]


def enroll_voice(
    audio: Sequence[float],
    ambient_ms: int,
    mouth: Sequence[tuple[int, float]],
    analyzer: Optional[AudioAnalyzer] = None,
    extractor: Optional[vp.EmbeddingExtractor] = None,
) -> dict[str, Any]:
    """``mouth`` holds (ms from the recording start, aperture); ``ambient_ms`` is the leading silence segment."""
    extractor = extractor or vp.default_extractor()
    analyzer = analyzer or AudioAnalyzer(InMemoryStateStore(), extractor=extractor)
    samples = np.clip(np.nan_to_num(np.asarray(audio, dtype=np.float32), nan=0.0), -1.0, 1.0)
    split = ambient_ms * t.AUDIO_SAMPLE_RATE // 1000
    if samples.size - split < t.VOICEPRINT_MIN_ENROLL_VOICED_S * t.AUDIO_SAMPLE_RATE:
        raise EnrollmentError("INSUFFICIENT_SPEECH")

    quiet = analyzer.analyze(samples[:split])
    if quiet.speech_detected or quiet.rms >= t.HIGH_NOISE_NON_SPEECH_RMS:
        raise EnrollmentError("AMBIENT_NOT_QUIET")
    phrase = samples[split:]
    measured = analyzer.analyze(phrase)
    if measured.speaker_model_unavailable:
        raise vp.SpeakerModelUnavailable("speaker models are unavailable")
    if measured.multiple_speakers:
        raise EnrollmentError("MULTIPLE_SPEAKERS")
    voiced = voiced_audio(phrase, measured.voiced_flags)
    if vp.voiced_seconds(voiced) < t.VOICEPRINT_MIN_ENROLL_VOICED_S:
        raise EnrollmentError("INSUFFICIENT_SPEECH")

    readings = [(at - ambient_ms, value) for at, value in mouth if at >= ambient_ms]
    verdict = lipsync.evaluate(measured.chunk_rms, measured.voiced_flags, readings, "telemetry").verdict
    if verdict == "insufficient":
        raise EnrollmentError("NO_MOUTH")
    if verdict == "unsynced":
        raise EnrollmentError("UNSYNCED")
    return vp.enroll(extractor, voiced, quiet.rms)
