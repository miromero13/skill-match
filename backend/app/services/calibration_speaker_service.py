"""Offline speaker diarization (sherpa-onnx) behind the integrity engine's ``AudioAnalyzer``.

Only the model access lives here now: the checks (one speaker, no overlap) are the engine's
(``integrity.calibration.CalibrationProfile.speech``) and the supervision's. The SHA-256 pins are verified before every
load and a missing or unverified model raises 503 (the analyzer reports it as an unavailable model: fail closed).
Offline diarization estimates; not speaker identity or an overlap guarantee.
"""
import hashlib
from pathlib import Path

from app.core.exceptions import SkillMatchException

MODEL_ROOT = Path(__file__).resolve().parents[1] / "models" / "weights" / "audio-integrity"
SEGMENTATION_MODEL = MODEL_ROOT / "speaker_segmentation.onnx"
EMBEDDING_MODEL = MODEL_ROOT / "speaker_embedding.onnx"
MODEL_HASHES = {
    "speaker_segmentation.onnx": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "speaker_embedding.onnx": "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
}


class CalibrationSpeakerService:
    @staticmethod
    def segments(audio):
        for model in (SEGMENTATION_MODEL, EMBEDDING_MODEL):
            if not model.is_file():
                raise SkillMatchException(statuscode=503, message="Los modelos locales de hablantes no están disponibles.")
            if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_HASHES[model.name]:
                raise SkillMatchException(statuscode=503, message="Los modelos locales de hablantes no superaron la verificación de integridad.")
        try:
            import sherpa_onnx
            config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
                segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                    pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                        model=str(SEGMENTATION_MODEL), window_shift_ratio=0.1,
                    ), num_threads=1,
                ),
                embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(EMBEDDING_MODEL), num_threads=1),
                clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.5),
                min_duration_on=0.2, min_duration_off=0.3,
            )
            if not config.validate():
                raise ValueError("Invalid local diarization configuration")
            # Separate instances avoid sharing mutable native inference state.
            diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
            return diarizer.process(audio).sort_by_start_time()
        except (ImportError, ValueError, RuntimeError) as exc:
            raise SkillMatchException(statuscode=503, message="No se pudo ejecutar la comprobación local de hablantes.") from exc
