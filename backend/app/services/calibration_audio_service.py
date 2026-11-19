"""Local WebRTC speech activity, not speaker/source identification or ASR."""
import numpy as np

from app.core.exceptions import SkillMatchException


class CalibrationAudioService:
    @staticmethod
    def detector():
        try:
            import webrtcvad
            return webrtcvad.Vad(3)
        except ImportError as exc:
            raise SkillMatchException(statuscode=503, message="El detector local de voz no está disponible.") from exc

    @classmethod
    def assess(cls, background, spoken):
        windows = []
        # A fresh detector per window avoids carrying speech history from the background.
        for samples, minimum, maximum in ((background, 32000, 64000), (spoken, 112000, 160000)):
            audio = np.asarray(samples, dtype=np.float32)
            if (audio.ndim != 1 or not minimum <= audio.size <= maximum
                    or not np.isfinite(audio).all() or np.any(np.abs(audio) > 1)):
                raise SkillMatchException(statuscode=400, message="El audio debe incluir fondo de 2 a 4 segundos y voz de 7 a 10 segundos a 16000 Hz.")
            detector = cls.detector()
            pcm = (audio * 32767).astype("<i2")
            flags = [detector.is_speech(pcm[index:index + 480].tobytes(), 16000)
                     for index in range(0, pcm.size - 479, 480)]
            run = maximum = 0
            for voiced in flags:
                run = run + 1 if voiced else 0
                maximum = max(maximum, run)
            windows.append((sum(flags), maximum, float(np.sqrt(np.mean(audio ** 2)))))
        ambient, speech = windows
        if ambient[0] >= 5 or ambient[1] >= 3:
            raise SkillMatchException(statuscode=400, message="Se detectó voz durante el silencio. Pausá llamadas, videos o conversaciones y repetí la comprobación.")
        if ambient[2] > 0.012:
            raise SkillMatchException(statuscode=400, message="Hay demasiado ruido de fondo. Buscá un ambiente más silencioso y repetí la comprobación.")
        if speech[0] < 10 or speech[1] < 3 or speech[2] < 0.003:
            raise SkillMatchException(statuscode=400, message="No se detectó voz suficiente. Decí «Estoy listo para comenzar» cuando se indique y repetí la comprobación.")
        return {"microphone": True, "background_quiet": True}
