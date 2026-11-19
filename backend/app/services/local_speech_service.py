"""Bounded, offline Whisper inference using explicitly provisioned local assets."""
import io
from pathlib import Path
import threading
import wave

import numpy as np

from app.core.config import settings
from app.core.exceptions import SkillMatchException


class LocalSpeechService:
    MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "weights" / "theory-whisper"
    _slots = threading.BoundedSemaphore(2)
    UNAVAILABLE = "La transcripción local no está disponible. Tu respuesta no fue registrada."

    @classmethod
    def ensure_available(cls):
        if not all((cls.MODEL_DIR / name).is_file() and (cls.MODEL_DIR / name).stat().st_size > 0
                   for name in ("encoder.onnx", "decoder.onnx", "tokens.txt")):
            raise SkillMatchException(statuscode=503, message=cls.UNAVAILABLE)
        if not settings.THEORY_ASR_ENABLED:
            raise SkillMatchException(statuscode=503, message="La transcripción local está deshabilitada en la configuración. Tu intento no se descontó.")

    @classmethod
    def transcribe(cls, audio_bytes: bytes) -> str:
        cls.ensure_available()
        paths = [cls.MODEL_DIR / name for name in ("encoder.onnx", "decoder.onnx", "tokens.txt")]
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as source:
                if (source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != 16000
                        or not 1600 <= source.getnframes() <= 16000 * 300
                        or source.getcomptype() != "NONE"):
                    raise ValueError("unsupported PCM format or duration")
                samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32) / 32768
                if len(samples) != source.getnframes():
                    raise ValueError("truncated PCM payload")
        except (EOFError, wave.Error, ValueError):
            raise SkillMatchException(statuscode=400, message="El audio debe ser WAV PCM mono de 16 kHz y 16 bits.")
        if not cls._slots.acquire(blocking=False):
            raise SkillMatchException(statuscode=503, message="La transcripción está ocupada. Tu respuesta no fue registrada.")
        try:
            import sherpa_onnx
            recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(paths[0]), decoder=str(paths[1]), tokens=str(paths[2]),
                language="es", task="transcribe", num_threads=1, provider="cpu", debug=False,
            )
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, samples)
            recognizer.decode_stream(stream)
            text = stream.result.text
            if not isinstance(text, str) or not text.strip() or len(text) > 16000:
                raise ValueError("no usable transcript")
            return text.strip()
        except Exception:
            raise SkillMatchException(statuscode=503, message=cls.UNAVAILABLE)
        finally:
            cls._slots.release()
