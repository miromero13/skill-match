"""Offline diarization estimates; not speaker identity or an overlap guarantee."""
import hashlib
import math
from pathlib import Path

from app.core.exceptions import SkillMatchException

MODEL_ROOT = Path(__file__).resolve().parents[1] / "models" / "weights" / "audio-integrity"
SEGMENTATION_MODEL = MODEL_ROOT / "speaker_segmentation.onnx"
EMBEDDING_MODEL = MODEL_ROOT / "speaker_embedding.onnx"
MODEL_HASHES = {
    "speaker_segmentation.onnx": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "speaker_embedding.onnx": "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
}


def reject(message):
    raise SkillMatchException(statuscode=400, message=message)


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

    @classmethod
    def assess(cls, audio):
        segments = list(cls.segments(audio))
        duration = len(audio) / 16000
        for item in segments:
            if (not math.isfinite(item.start) or not math.isfinite(item.end)
                    or not 0 <= item.start < item.end <= duration + 0.1 or item.speaker < 0):
                reject("No se pudo confirmar una sola voz con suficiente evidencia. Repetí la frase con voz clara.")
        for index, first in enumerate(segments):
            for second in segments[index + 1:]:
                if first.speaker != second.speaker and min(first.end, second.end) - max(first.start, second.start) >= 0.12:
                    reject("Se detectaron indicios de voces superpuestas. Buscá un ambiente sin conversaciones y repetí la comprobación.")
        speakers = {item.speaker for item in segments if item.end - item.start >= 0.2}
        if len(speakers) > 1:
            reject("Se detectaron indicios de más de una voz. Pausá llamadas y conversaciones y repetí la comprobación.")
        if len(speakers) != 1 or sum(item.end - item.start for item in segments) < 1.2:
            reject("No se pudo confirmar una sola voz con suficiente evidencia. Repetí la frase con voz clara.")
        return {"single_speaker": True, "no_overlap": True}
