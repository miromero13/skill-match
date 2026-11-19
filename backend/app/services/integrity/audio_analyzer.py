"""Audio measurements: RMS/noise, WebRTC VAD and multi-speaker diarization with a rolling per-session buffer.

Measures only: the incident decision (HIGH_NOISE, MULTIPLE_SPEAKERS, ...) belongs to the policy profile.
Diarization reuses ``CalibrationSpeakerService.segments`` (Sherpa-ONNX Pyannote + embeddings, local).

Calibration mapping (T9): ``CalibrationAudioService`` (RMS + VAD speech checks) maps to ``AudioAnalyzer.analyze``;
``CalibrationSpeakerService.assess`` (single speaker, no overlap) maps to ``AudioAnalyzer.detect_multiple_speakers``.
"""
import logging
from typing import Any, Callable, Iterable, Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import AudioObservation
from app.services.integrity.state import SessionStateStore

logger = logging.getLogger("skillmatch.continuous_supervision")

SegmentsProvider = Callable[[np.ndarray], Iterable[Any]]


def _default_segments(audio: np.ndarray) -> Iterable[Any]:
    # Resolved at call time so the (heavy) speaker module is only imported when diarization runs.
    from app.services.calibration_speaker_service import CalibrationSpeakerService

    return CalibrationSpeakerService.segments(audio)


class AudioAnalyzer:
    """Analyzes 16 kHz mono windows; the rolling buffer of voiced audio lives in the injected state store."""

    def __init__(self, state: SessionStateStore, speaker_segments: Optional[SegmentsProvider] = None) -> None:
        self.state = state
        self.speaker_segments: SegmentsProvider = speaker_segments or _default_segments

    @staticmethod
    def is_missing(samples: Optional[Sequence[float]], duration_ms: Optional[int]) -> bool:
        """True when audio is absent, too short, or inconsistent with ``duration_ms`` at 16 kHz."""
        if not samples or len(samples) < t.AUDIO_MIN_SAMPLES:
            return True
        if duration_ms is None:
            return False
        expected = duration_ms * t.AUDIO_SAMPLE_RATE / 1000.0
        return abs(len(samples) - expected) > t.AUDIO_LENGTH_TOLERANCE * expected

    def detect_multiple_speakers(
        self, audio: np.ndarray, voiced_flags: list[bool], session_key: Optional[str]
    ) -> bool:
        """Detects several speakers or overlapping voices over the window plus the buffered voiced audio."""
        voiced_chunks = sum(1 for v in voiced_flags if v)
        # Only windows with real voice activity are remembered and concatenated
        combined = self.state.combine_with_previous(
            session_key, audio, remember=voiced_chunks >= t.DIARIZATION_REMEMBER_MIN_VOICED_CHUNKS
        )

        # Require at least 1.5 s of audio with sufficient speech before running diarization
        if combined.size >= t.DIARIZATION_MIN_SAMPLES and voiced_chunks >= t.DIARIZATION_MIN_VOICED_CHUNKS:
            try:
                segments = list(self.speaker_segments(combined))
                speakers = {
                    item.speaker
                    for item in segments
                    if (item.end - item.start) >= t.SPEAKER_MIN_DURATION_S and item.speaker >= 0
                }
                if len(speakers) > 1:
                    return True
                for i, first in enumerate(segments):
                    for second in segments[i + 1:]:
                        if (
                            first.speaker != second.speaker
                            and min(first.end, second.end) - max(first.start, second.start)
                            >= t.SPEAKER_OVERLAP_MIN_S
                        ):
                            return True
            except Exception as exc:
                logger.debug("Error en diarización continua: %s", exc)

        return False

    def analyze(self, samples: Optional[Sequence[float]], session_key: Optional[str] = None) -> AudioObservation:
        """Measures RMS, strict WebRTC VAD(3) speech and (when speech is present) multiple speakers."""
        if not samples or len(samples) < t.AUDIO_MIN_SAMPLES:
            return AudioObservation()

        audio = np.asarray(samples, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        audio = np.clip(audio, -1.0, 1.0)
        audio = audio - float(np.mean(audio))
        rms = float(np.sqrt(np.mean(np.square(audio))))

        speech_detected = False
        chunk_size = t.VAD_CHUNK_SAMPLES
        total_chunks = audio.size // chunk_size
        chunk_rms = np.zeros(0, dtype=np.float32)
        voiced_flags: list[bool] = []

        # Only run VAD above the ambient silence floor; quiet room noise is never amplified for the VAD
        if total_chunks > 0 and rms >= t.SILENCE_RMS_FLOOR:
            chunks = audio[: total_chunks * chunk_size].reshape(total_chunks, chunk_size)
            chunk_rms = np.sqrt(np.mean(np.square(chunks), axis=1))
            pcm = (audio * 32767).astype("<i2")

            try:
                import webrtcvad

                vad = webrtcvad.Vad(t.VAD_AGGRESSIVENESS)
                for i in range(total_chunks):
                    is_voiced = False
                    if chunk_rms[i] >= t.SILENCE_RMS_FLOOR:
                        raw_bytes = pcm[i * chunk_size : (i + 1) * chunk_size].tobytes()
                        if vad.is_speech(raw_bytes, t.AUDIO_SAMPLE_RATE):
                            is_voiced = True
                    voiced_flags.append(is_voiced)

                # Require both enough voiced chunks (180 ms) AND a contiguous run (90 ms)
                run = max_run = 0
                for v in voiced_flags:
                    run = run + 1 if v else 0
                    max_run = max(max_run, run)

                if sum(voiced_flags) >= t.VAD_MIN_VOICED_CHUNKS and max_run >= t.VAD_MIN_CONTIGUOUS_CHUNKS:
                    speech_detected = True
            except Exception as exc:
                logger.debug("VAD no disponible o error en procesamiento: %s", exc)

        # A silent window clears the rolling buffer so stale speech is not carried over
        if not speech_detected and session_key:
            self.state.clear_voiced_audio(session_key)

        high_noise = rms > t.HIGH_NOISE_RMS or (rms > t.HIGH_NOISE_NON_SPEECH_RMS and not speech_detected)

        multiple_speakers = False
        if speech_detected:
            multiple_speakers = self.detect_multiple_speakers(audio, voiced_flags, session_key)

        return AudioObservation(
            rms=rms,
            speech_detected=speech_detected,
            multiple_speakers=multiple_speakers,
            high_noise=high_noise,
            chunk_rms=chunk_rms,
            voiced_flags=voiced_flags,
        )
