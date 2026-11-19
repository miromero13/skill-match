"""Voice calibration: turns a recorded control phrase into a voiceprint (S3, S4, S11), for the trial and the pre-exam.

The recording is a short silence segment (the ambient floor, later used for BACKGROUND_AUDIO) followed by the
candidate reading a phrase aloud, with the mouth-aperture readings captured meanwhile. The same analyzers that
supervise the exam judge it, as guided checks that must pass:

  * the silence segment has neither speech nor loud noise;
  * enough voiced speech (>= 3 s) and one voice only (diarization: no several speakers, no overlap);
  * the browser's mouth readings agree with the JPEG frames the server measured itself (the CLIENT_MISMATCH
    mechanism, ``gaze.check_mouth_telemetry``): untrusted telemetry rejects the enrollment;
  * the voice follows the mouth (lip-sync correlation), so a played recording cannot be enrolled;
  * the voice segments are mutually consistent (``voiceprint.enroll``).

Failures raise ``EnrollmentError`` (``code`` says why); a missing or unusable speaker model raises
``voiceprint.SpeakerModelUnavailable``: calibration fails closed, there is no unverified enrollment.
``measure_recording`` and ``finish_enrollment`` are the two halves of ``enroll_voice`` so the pre-exam calibration
can judge the measurements in between with its own, stricter, profile (``calibration.py``).
"""
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

import numpy as np

from app.services.integrity import lipsync, thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.audio_analyzer import AudioAnalyzer, voiced_audio
from app.services.integrity.gaze import check_mouth_telemetry
from app.services.integrity.models import AudioObservation, GazeSample
from app.services.integrity.state import InMemoryStateStore
from app.services.integrity.voiceprint import EnrollmentError

__all__ = ["EnrollmentError", "InMemoryStateStore", "Recording", "RecordingRules", "TrialRules", "enroll_voice",
           "finish_enrollment", "judge_sync", "measure_recording"]

MouthReadings = Sequence[tuple[int, float]]  # (ms from the recording start, mouth aperture)


@dataclass(frozen=True)
class Recording:
    """A voice recording split into its silence segment and its speech segment, both measured."""

    samples: np.ndarray
    split: int  # first sample of the speech segment
    quiet: AudioObservation
    phrase: np.ndarray
    measured: AudioObservation
    voiced: np.ndarray


class RecordingRules(Protocol):
    """What a caller requires of the measured silence and speech segments; each raises when its rule fails."""

    def ambient(self, quiet: AudioObservation, segment: np.ndarray) -> None:
        """The silence segment (``segment`` are its raw samples)."""

    def speech(self, measured: AudioObservation, phrase: np.ndarray, voiced: np.ndarray) -> None:
        """The speech segment: its measurement, raw samples and the voiced samples only."""


class TrialRules:
    """The trial's rules: a quiet room, one voice and at least 3 s of voiced speech."""

    def ambient(self, quiet: AudioObservation, segment: np.ndarray) -> None:
        if quiet.speech_detected or quiet.rms >= t.HIGH_NOISE_NON_SPEECH_RMS:
            raise EnrollmentError("AMBIENT_NOT_QUIET")

    def speech(self, measured: AudioObservation, phrase: np.ndarray, voiced: np.ndarray) -> None:
        if measured.multiple_speakers:
            raise EnrollmentError("MULTIPLE_SPEAKERS")
        if vp.voiced_seconds(voiced) < t.VOICEPRINT_MIN_ENROLL_VOICED_S:
            raise EnrollmentError("INSUFFICIENT_SPEECH")


def measure_recording(
    audio: Sequence[float], ambient_ms: int, analyzer: AudioAnalyzer, rules: Optional[RecordingRules] = None
) -> Recording:
    """Measures the silence segment and the speech segment (VAD, diarization); ``rules`` judges each one in turn."""
    rules = rules or TrialRules()
    samples = np.clip(np.nan_to_num(np.asarray(audio, dtype=np.float32), nan=0.0), -1.0, 1.0)
    split = ambient_ms * t.AUDIO_SAMPLE_RATE // 1000
    if samples.size - split < t.VOICEPRINT_MIN_ENROLL_VOICED_S * t.AUDIO_SAMPLE_RATE:
        raise EnrollmentError("INSUFFICIENT_SPEECH")
    quiet = analyzer.analyze(samples[:split])
    rules.ambient(quiet, samples[:split])
    phrase = samples[split:]
    measured = analyzer.analyze(phrase)
    if measured.speaker_model_unavailable:
        raise vp.SpeakerModelUnavailable("speaker models are unavailable")
    voiced = voiced_audio(phrase, measured.voiced_flags)
    rules.speech(measured, phrase, voiced)
    return Recording(samples, split, quiet, phrase, measured, voiced)


def judge_sync(
    recording: Recording,
    ambient_ms: int,
    mouth: Optional[MouthReadings],
    server_mouth: Optional[MouthReadings],
) -> None:
    """Cross-checks the mouth telemetry and judges lip-sync (the voice must follow the mouth).

    ``mouth`` is the browser's telemetry and ``server_mouth`` the aperture the server measured on the sampled JPEG
    frames (one reading per frame with exactly one face), both as (ms from the recording start, aperture).
      * ``mouth`` None: there is no telemetry; the server's own readings are the series (source "server").
      * ``server_mouth`` None: no frames to cross-check against (the trial endpoint until it sends frames).
      * both given: untrusted telemetry (``gaze.check_mouth_telemetry``) rejects with UNTRUSTED_TELEMETRY.
    """
    def samples(readings: MouthReadings) -> list[GazeSample]:
        return [GazeSample(t_ms=int(at), face_count=1, mouth_open=float(value)) for at, value in readings]

    series, source = mouth, "telemetry"
    if mouth is None:
        series, source = server_mouth, "server"
    elif server_mouth is not None and mouth and not check_mouth_telemetry(samples(server_mouth), samples(mouth)).trusted:
        raise EnrollmentError("UNTRUSTED_TELEMETRY")
    if not series:
        raise EnrollmentError("NO_MOUTH")
    readings = [(at - ambient_ms, value) for at, value in series if at >= ambient_ms]
    measured = recording.measured
    verdict = lipsync.evaluate(measured.chunk_rms, measured.voiced_flags, readings, source).verdict
    if verdict == "insufficient":
        raise EnrollmentError("NO_MOUTH")
    if verdict == "unsynced":
        raise EnrollmentError("UNSYNCED")


def finish_enrollment(
    recording: Recording,
    ambient_ms: int,
    mouth: Optional[MouthReadings],
    server_mouth: Optional[MouthReadings],
    extractor: vp.EmbeddingExtractor,
) -> dict[str, Any]:
    """``judge_sync`` and then the voiceprint record built from the candidate's voiced calibration speech."""
    judge_sync(recording, ambient_ms, mouth, server_mouth)
    return vp.enroll(extractor, recording.voiced, recording.quiet.rms)


def enroll_voice(
    audio: Sequence[float],
    ambient_ms: int,
    mouth: MouthReadings,
    server_mouth: Optional[MouthReadings] = None,
    analyzer: Optional[AudioAnalyzer] = None,
    extractor: Optional[vp.EmbeddingExtractor] = None,
) -> dict[str, Any]:
    """``mouth`` holds (ms from the recording start, aperture); ``ambient_ms`` is the leading silence segment."""
    extractor = extractor or vp.default_extractor()
    analyzer = analyzer or AudioAnalyzer(InMemoryStateStore(), extractor=extractor)
    recording = measure_recording(audio, ambient_ms, analyzer)
    return finish_enrollment(recording, ambient_ms, mouth, server_mouth, extractor)
