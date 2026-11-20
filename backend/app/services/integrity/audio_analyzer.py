"""Audio measurements: RMS/noise, WebRTC VAD and multi-speaker diarization with a rolling per-session buffer.

Measures only: the incident decision (HIGH_NOISE, MULTIPLE_SPEAKERS, ...) belongs to the policy profile.
Diarization reuses ``CalibrationSpeakerService.segments`` (Sherpa-ONNX Pyannote + embeddings, local).

Device playback (S4): a browser cannot tell that the laptop itself is playing audio, so it is covered by
composition rather than by one detector. Played speech is caught by VOICE_MISMATCH (not the enrolled voice),
by LIP_SYNC_MISMATCH / VOICE_DETECTED (a voice with no matching mouth movement) and by MULTIPLE_SPEAKERS (it
adds a voice). Played non-speech (music, tones, TV) is caught by BACKGROUND_AUDIO: audio the VAD does not call
speech, above the ambient floor measured at voice calibration, for >= 2 s. HIGH_NOISE stays for very loud audio.

Calibration (T9) measures its recordings with this same analyzer, built with two knobs: ``vad_floor`` (0 feeds every
chunk to the VAD, as the pre-exam silence check always did) and ``min_speaker_s`` (a speaker counts from 0.2 s).
"""
import logging
import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.models import AudioObservation
from app.services.integrity.state import SessionStateStore

logger = logging.getLogger("skillmatch.continuous_supervision")

SegmentsProvider = Callable[[np.ndarray], Iterable[Any]]


@dataclass(frozen=True)
class SpeakerReport:
    """What diarization of the voiced buffer found; ``model_unavailable`` means it could not run (fail closed)."""

    diarized: bool = False
    speakers: int = 0
    overlap_s: float = 0.0
    foreign_voice: bool = False
    model_unavailable: bool = False

    @property
    def multiple(self) -> bool:
        return self.speakers > 1 or self.overlap_s >= t.SPEAKER_OVERLAP_MIN_S


def run_stats(flags: Sequence[Optional[bool]]) -> tuple[int, int]:
    """(voiced chunks, longest run of consecutive voiced chunks) of a VAD flag series."""
    run = longest = 0
    for flag in flags:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    return sum(1 for flag in flags if flag), longest


def signal_rms(samples: Sequence[float]) -> float:
    """Plain RMS of the samples (no DC removal): the loudness the pre-exam checks have always used."""
    audio = np.asarray(samples, dtype=np.float32)
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def voiced_audio(audio: np.ndarray, voiced_flags: Sequence[bool]) -> np.ndarray:
    """The samples of the chunks the VAD called speech, in order."""
    size = t.VAD_CHUNK_SAMPLES
    parts = [audio[i * size:(i + 1) * size] for i, flag in enumerate(voiced_flags) if flag]
    return np.concatenate(parts).astype(np.float32) if parts else np.zeros(0, dtype=np.float32)


def _default_segments(audio: np.ndarray) -> Iterable[Any]:
    # Resolved at call time so the (heavy) speaker module is only imported when diarization runs.
    from app.services.calibration_speaker_service import CalibrationSpeakerService

    return CalibrationSpeakerService.segments(audio)


class AudioAnalyzer:
    """Analyzes 16 kHz mono windows; the rolling buffer of voiced audio lives in the injected state store."""

    def __init__(
        self,
        state: SessionStateStore,
        speaker_segments: Optional[SegmentsProvider] = None,
        extractor: Optional[vp.EmbeddingExtractor] = None,
        vad_floor: float = t.SILENCE_RMS_FLOOR,
        min_speaker_s: float = t.SPEAKER_MIN_DURATION_S,
    ) -> None:
        self.state = state
        self.vad_floor = vad_floor
        self.min_speaker_s = min_speaker_s
        self.speaker_segments: SegmentsProvider = speaker_segments or _default_segments
        self.extractor: vp.EmbeddingExtractor = extractor or vp.default_extractor()

    @staticmethod
    def is_missing(samples: Optional[Sequence[float]], duration_ms: Optional[int]) -> bool:
        """True when audio is absent, too short, or inconsistent with ``duration_ms`` at 16 kHz."""
        if not samples or len(samples) < t.AUDIO_MIN_SAMPLES:
            return True
        if duration_ms is None:
            return False
        expected = duration_ms * t.AUDIO_SAMPLE_RATE / 1000.0
        return abs(len(samples) - expected) > t.AUDIO_LENGTH_TOLERANCE * expected

    def diarize(
        self, buffer: np.ndarray, window_voiced_chunks: int, voiceprint: Optional[Mapping[str, Any]] = None
    ) -> SpeakerReport:
        """Diarizes the trial's rolling voiced buffer (S2) with the existing minimum-duration filters.

        With an enrolled voiceprint, a cluster that is not that voice next to one that is makes ``foreign_voice``.
        A diarization that cannot run (models missing, inference error) is ``model_unavailable``, not "one voice".
        """
        # Require at least 1.5 s of buffered speech and a window with real speech before running diarization
        if buffer.size < t.DIARIZATION_MIN_SAMPLES or window_voiced_chunks < t.DIARIZATION_MIN_VOICED_CHUNKS:
            return SpeakerReport()
        try:
            segments = list(self.speaker_segments(buffer))
        except Exception as exc:
            logger.warning("Diarización continua no disponible: %s", exc)
            return SpeakerReport(model_unavailable=True)
        duration = buffer.size / t.AUDIO_SAMPLE_RATE
        if any(not (math.isfinite(item.start) and math.isfinite(item.end)) or item.start < 0 or item.end <= item.start
               or item.end > duration + t.DIARIZATION_SEGMENT_SLACK_S for item in segments):
            # Segments outside the audio that was diarized (as the pre-exam check always rejected) are never trusted.
            logger.warning("Diarización con intervalos inválidos: se descarta (nunca una sola voz).")
            return SpeakerReport(model_unavailable=True)
        usable = [item for item in segments if item.speaker >= 0]
        kept = [item for item in usable if (item.end - item.start) >= self.min_speaker_s]
        speakers = {item.speaker for item in kept}
        overlap = max(
            (
                min(first.end, second.end) - max(first.start, second.start)
                for i, first in enumerate(usable)
                for second in usable[i + 1:]
                if first.speaker != second.speaker
            ),
            default=0.0,
        )
        foreign = False
        if voiceprint is not None and len(speakers) > 1:
            try:
                foreign = self._has_foreign_cluster(buffer, kept, voiceprint)
            except vp.SpeakerModelUnavailable as exc:
                logger.warning("Huella de voz no disponible para comparar hablantes: %s", exc)
                return SpeakerReport(True, len(speakers), max(0.0, overlap), model_unavailable=True)
        return SpeakerReport(True, len(speakers), max(0.0, overlap), foreign)

    def _has_foreign_cluster(self, buffer: np.ndarray, kept: Sequence[Any], voiceprint: Mapping[str, Any]) -> bool:
        """True when one diarized cluster matches the voiceprint and another one clearly does not."""
        by_speaker: dict[int, list[np.ndarray]] = {}
        for item in kept:
            piece = buffer[max(0, int(item.start * t.AUDIO_SAMPLE_RATE)):int(item.end * t.AUDIO_SAMPLE_RATE)]
            by_speaker.setdefault(item.speaker, []).append(piece)
        statuses = []
        for pieces in by_speaker.values():
            statuses.append(vp.match_voice(
                self.extractor, voiceprint, np.concatenate(pieces), min_voiced_s=t.VOICEPRINT_CLUSTER_MIN_VOICED_S,
            ).status)
        return "match" in statuses and "mismatch" in statuses

    def detect_multiple_speakers(
        self, audio: np.ndarray, voiced_flags: list[bool], session_key: Optional[str]
    ) -> bool:
        """Detects several speakers or overlapping voices over the trial's buffered voiced audio (unconfirmed)."""
        voiced_chunks = sum(1 for v in voiced_flags if v)
        buffer = self.state.append_voiced(
            session_key, voiced_audio(audio, voiced_flags), t.VOICE_BUFFER_MAX_SAMPLES
        )
        return self.diarize(buffer, voiced_chunks).multiple

    def verify_voice(
        self, buffer: np.ndarray, voiceprint: Optional[Mapping[str, Any]]
    ) -> tuple[str, Optional[float], bool]:
        """(status, similarity, model_unavailable) of the buffered voiced speech against the voiceprint (S3, S11)."""
        if buffer.size < t.VOICEPRINT_MIN_VERIFY_VOICED_S * t.AUDIO_SAMPLE_RATE:
            return "insufficient", None, False
        if voiceprint is None:
            return "unenrolled", None, False
        try:
            result = vp.match_voice(self.extractor, voiceprint, buffer)
        except vp.SpeakerModelUnavailable as exc:
            logger.warning("Huella de voz no disponible: %s", exc)
            return "insufficient", None, True
        return result.status, result.similarity, False

    @staticmethod
    def background_flags(
        chunk_rms: np.ndarray, voiced_flags: Sequence[bool], ambient_rms: Optional[float]
    ) -> list[Optional[bool]]:
        """Per chunk: non-speech audible above the ambient floor but short of very loud (that is HIGH_NOISE).

        Speech and very loud chunks give no verdict (they neither extend nor end a run); quiet ones end it.
        """
        floor = max(t.BACKGROUND_MIN_RMS, t.BACKGROUND_AMBIENT_FACTOR * (ambient_rms or 0.0))
        flags: list[Optional[bool]] = []
        for rms, voiced in zip(chunk_rms, voiced_flags):
            if voiced or rms >= t.HIGH_NOISE_NON_SPEECH_RMS:
                flags.append(None)
            else:
                flags.append(bool(rms >= floor))
        return flags

    def analyze(
        self,
        samples: Optional[Sequence[float]],
        session_key: Optional[str] = None,
        voiceprint: Optional[Mapping[str, Any]] = None,
    ) -> AudioObservation:
        """Measures RMS, strict WebRTC VAD(3) speech, speakers over the voiced buffer and background audio."""
        if samples is None or len(samples) < t.AUDIO_MIN_SAMPLES:
            return AudioObservation()
        vad_unavailable = False

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
        if total_chunks > 0 and rms >= self.vad_floor:
            chunks = audio[: total_chunks * chunk_size].reshape(total_chunks, chunk_size)
            chunk_rms = np.sqrt(np.mean(np.square(chunks), axis=1))
            pcm = (audio * 32767).astype("<i2")

            try:
                import webrtcvad

                vad = webrtcvad.Vad(t.VAD_AGGRESSIVENESS)
                for i in range(total_chunks):
                    is_voiced = False
                    if chunk_rms[i] >= self.vad_floor:
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
                vad_unavailable = True
                logger.debug("VAD no disponible o error en procesamiento: %s", exc)

        high_noise = rms > t.HIGH_NOISE_RMS or (rms > t.HIGH_NOISE_NON_SPEECH_RMS and not speech_detected)

        report = SpeakerReport()
        voice_status: Optional[str] = None
        similarity: Optional[float] = None
        voice_model_missing = voice_reset = False
        if speech_detected:
            buffer = self.state.append_voiced(
                session_key, voiced_audio(audio, voiced_flags), t.VOICE_BUFFER_MAX_SAMPLES
            )
            report = self.diarize(buffer, sum(1 for v in voiced_flags if v), voiceprint)
            voice_status, similarity, voice_model_missing = self.verify_voice(buffer, voiceprint)
        else:
            # Stale speech is forgotten after a long enough silence
            voice_reset = self.state.note_silence(session_key, audio.size, t.VOICE_BUFFER_SILENCE_CLEAR_SAMPLES)

        ambient = vp.ambient_rms_of(voiceprint) if voiceprint is not None else None
        return AudioObservation(
            rms=rms,
            speech_detected=speech_detected,
            multiple_speakers=report.multiple,
            high_noise=high_noise,
            chunk_rms=chunk_rms,
            voiced_flags=voiced_flags,
            diarized=report.diarized,
            speakers=report.speakers,
            overlap_s=report.overlap_s,
            foreign_voice=report.foreign_voice,
            speaker_model_unavailable=report.model_unavailable or voice_model_missing,
            voice_status=voice_status,  # type: ignore[arg-type]
            voice_similarity=similarity,
            voiced_chunks=sum(1 for v in voiced_flags if v),
            voice_reset=voice_reset,
            background_flags=self.background_flags(chunk_rms, voiced_flags, ambient),
            vad_unavailable=vad_unavailable,
        )
