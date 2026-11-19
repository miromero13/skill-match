"""Voiceprints: who is speaking (S3, S11).

A voiceprint is the L2-normalized mean of 3D-Speaker ERes2Net embeddings (sherpa-onnx, local, the same
SHA-256-pinned ``speaker_embedding.onnx`` the diarization uses) of the candidate's voiced speech at calibration.
During supervision the voiced audio of a trial is embedded again and compared by cosine similarity.

Rules that keep it honest:
  * too little voiced speech is "insufficient", never a verdict (no match, no mismatch);
  * a missing or unpinned model raises ``SpeakerModelUnavailable``: callers fail closed (MODEL_UNAVAILABLE),
    never a clean pass;
  * the embedding is a biometric: it is stored on the trial and never serialized into any response.
"""
import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Optional, Protocol

import numpy as np

from app.services.calibration_speaker_service import EMBEDDING_MODEL, MODEL_HASHES
from app.services.integrity import thresholds as t

logger = logging.getLogger("skillmatch.continuous_supervision")

RECORD_VERSION = 1
MODEL_NAME = "3dspeaker_eres2net_base_sv_zh-cn_16k"


class SpeakerModelUnavailable(Exception):
    """The speaker embedding model is missing, unpinned or unusable (or a stored voiceprint is unreadable)."""


class EnrollmentError(Exception):
    """The calibration speech cannot yield a trustworthy voiceprint; ``code`` says why (the API maps it)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EmbeddingExtractor(Protocol):
    def embed(self, audio: np.ndarray) -> np.ndarray:
        """Embedding of 16 kHz mono float audio; raises ``SpeakerModelUnavailable`` when the model is unusable."""


_MODEL_CHECK_LOCK = threading.Lock()
_VERIFIED_MODELS: dict[str, str] = {}  # path -> mtime/size fingerprint already hashed against the pin


def _model_fingerprint() -> str:
    stat = EMBEDDING_MODEL.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _check_model() -> None:
    """Raises ``SpeakerModelUnavailable`` unless the embedding model exists and matches its pinned SHA-256."""
    if not EMBEDDING_MODEL.is_file():
        raise SpeakerModelUnavailable("speaker embedding model is not installed")
    key, fingerprint = str(EMBEDDING_MODEL), _model_fingerprint()
    with _MODEL_CHECK_LOCK:
        if _VERIFIED_MODELS.get(key) == fingerprint:
            return
        digest = hashlib.sha256(EMBEDDING_MODEL.read_bytes()).hexdigest()
        if digest not in MODEL_HASHES["speaker_embedding.onnx"]:
            raise SpeakerModelUnavailable("speaker embedding model failed its integrity check")
        _VERIFIED_MODELS[key] = fingerprint


def model_available() -> bool:
    try:
        _check_model()
    except SpeakerModelUnavailable:
        return False
    return True


class SherpaEmbeddingExtractor:
    """sherpa-onnx ``SpeakerEmbeddingExtractor`` over the pinned model; loaded once, serialized by a lock."""

    _lock = threading.Lock()
    _extractor: Any = None
    _extractor_model: Optional[str] = None

    def _load(self) -> Any:
        _check_model()
        cls = type(self)
        if cls._extractor is None or cls._extractor_model != str(EMBEDDING_MODEL):
            try:
                import sherpa_onnx

                config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMBEDDING_MODEL), num_threads=1)
                if not config.validate():
                    raise ValueError("invalid speaker embedding configuration")
                cls._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
                cls._extractor_model = str(EMBEDDING_MODEL)
            except (ImportError, ValueError, RuntimeError) as exc:
                raise SpeakerModelUnavailable("speaker embedding model could not be loaded") from exc
        return cls._extractor

    def embed(self, audio: np.ndarray) -> np.ndarray:
        samples = np.ascontiguousarray(audio, dtype=np.float32)
        with self._lock:
            extractor = self._load()
            try:
                stream = extractor.create_stream()
                stream.accept_waveform(t.AUDIO_SAMPLE_RATE, samples)
                stream.input_finished()
                if not extractor.is_ready(stream):
                    raise SpeakerModelUnavailable("not enough audio for an embedding")
                vector = np.asarray(extractor.compute(stream), dtype=np.float32)
            except SpeakerModelUnavailable:
                raise
            except (RuntimeError, ValueError) as exc:
                raise SpeakerModelUnavailable("speaker embedding inference failed") from exc
        if vector.ndim != 1 or vector.size == 0 or not np.all(np.isfinite(vector)):
            raise SpeakerModelUnavailable("speaker embedding model returned an unusable embedding")
        return vector


def default_extractor() -> EmbeddingExtractor:
    return SherpaEmbeddingExtractor()


# ---- math -------------------------------------------------------------------------------------------


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(values))
    return values / norm if norm > 0.0 else values


def cosine(first: np.ndarray, second: np.ndarray) -> float:
    """Cosine similarity in [-1, 1]; a zero vector matches nothing (0.0)."""
    a, b = np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator > 0.0 else 0.0


def voiced_seconds(audio: np.ndarray) -> float:
    return float(np.asarray(audio).size) / t.AUDIO_SAMPLE_RATE


# ---- stored record ----------------------------------------------------------------------------------


def embedding_of(record: Optional[Mapping[str, Any]]) -> np.ndarray:
    """The unit embedding of a stored voiceprint; a malformed record is unusable (never trusted)."""
    try:
        values = np.asarray((record or {})["embedding"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise SpeakerModelUnavailable("stored voiceprint is unreadable") from exc
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)) or not np.any(values):
        raise SpeakerModelUnavailable("stored voiceprint is unreadable")
    return l2_normalize(values)


def ambient_rms_of(record: Optional[Mapping[str, Any]]) -> Optional[float]:
    """The ambient noise floor measured at calibration, or None when the record has none."""
    try:
        value = float((record or {})["ambient_rms"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if np.isfinite(value) and value >= 0.0 else None


# ---- matching ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceMatch:
    status: Literal["match", "mismatch", "insufficient"]
    similarity: Optional[float] = None


def match_voice(
    extractor: EmbeddingExtractor,
    record: Mapping[str, Any],
    voiced: np.ndarray,
    min_voiced_s: float = t.VOICEPRINT_MIN_VERIFY_VOICED_S,
    threshold: float = t.VOICEPRINT_MATCH_THRESHOLD,
) -> VoiceMatch:
    """Compares voiced speech with the enrolled voiceprint. Below ``min_voiced_s`` nothing is embedded or judged."""
    enrolled = embedding_of(record)
    if voiced_seconds(voiced) < min_voiced_s:
        return VoiceMatch("insufficient")
    similarity = cosine(enrolled, extractor.embed(voiced))
    return VoiceMatch("match" if similarity >= threshold else "mismatch", similarity)


# ---- enrollment -------------------------------------------------------------------------------------


def _segments(voiced: np.ndarray) -> list[np.ndarray]:
    """Consecutive ~2 s segments; a trailing remainder too short to embed is folded into the previous one."""
    size = int(t.VOICEPRINT_SEGMENT_S * t.AUDIO_SAMPLE_RATE)
    minimum = int(t.VOICEPRINT_MIN_VERIFY_VOICED_S * t.AUDIO_SAMPLE_RATE)
    pieces = [voiced[start:start + size] for start in range(0, voiced.size, size)]
    if len(pieces) > 1 and pieces[-1].size < minimum:
        pieces[-2] = np.concatenate([pieces[-2], pieces.pop()])
    return pieces


def enroll(extractor: EmbeddingExtractor, voiced: np.ndarray, ambient_rms: float) -> dict[str, Any]:
    """Builds the voiceprint record from the candidate's voiced calibration speech.

    Rejects (``EnrollmentError``) too little speech and segments that are not mutually consistent (more than one
    voice). Multi-speaker diarization and lip-sync are checked by the caller before any embedding is computed.
    """
    voiced = np.asarray(voiced, dtype=np.float32)
    if voiced_seconds(voiced) < t.VOICEPRINT_MIN_ENROLL_VOICED_S:
        raise EnrollmentError("INSUFFICIENT_SPEECH")
    pieces = _segments(voiced)
    if len(pieces) < t.VOICEPRINT_MIN_SEGMENTS:
        raise EnrollmentError("INSUFFICIENT_SPEECH")
    embeddings = [l2_normalize(extractor.embed(piece)) for piece in pieces]
    lowest = min(cosine(a, b) for i, a in enumerate(embeddings) for b in embeddings[i + 1:])
    if lowest < t.VOICEPRINT_ENROLL_MIN_CONSISTENCY:
        raise EnrollmentError("INCONSISTENT")
    mean = l2_normalize(np.mean(embeddings, axis=0))
    return {
        "version": RECORD_VERSION,
        "model": MODEL_NAME,
        "embedding": [float(value) for value in mean],
        "ambient_rms": float(max(0.0, ambient_rms)),
        "voiced_s": voiced_seconds(voiced),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
