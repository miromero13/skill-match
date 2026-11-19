"""Best-effort mouth-motion/audio correspondence, not semantic lip reading or PAD."""
import json

import cv2
import numpy as np

from app.core.exceptions import SkillMatchException
from app.services.calibration_audio_service import CalibrationAudioService


def reject(message):
    raise SkillMatchException(statuscode=400, message=message)


class CalibrationAVService:
    @staticmethod
    def voice_activity(audio):
        detector = CalibrationAudioService.detector()
        pcm = (np.asarray(audio, dtype=np.float32) * 32767).astype("<i2")
        return [(index / 16000 + .015, detector.is_speech(pcm[index:index + 480].tobytes(), 16000))
                for index in range(0, pcm.size - 479, 480)]

    @staticmethod
    def mouth_trace(frames, enrollment):
        from app.services.calibration_vision_service import CalibrationVisionService
        detector, recognizer = CalibrationVisionService.models()
        try:
            reference = np.asarray(json.loads(enrollment), dtype=np.float32)
        except (ValueError, TypeError) as exc:
            raise SkillMatchException(statuscode=400, message="Tu referencia biométrica no es válida. Volvé a registrar tu rostro.") from exc
        if reference.shape != (128,) or not np.isfinite(reference).all() or np.linalg.norm(reference) < 1e-6:
            reject("Tu referencia biométrica no es válida. Volvé a registrar tu rostro.")
        reference /= np.linalg.norm(reference)
        previous = None
        rectangle = None
        trace = []
        # Check identity at the beginning, middle and end, presence in every image.
        identity_samples = {0, len(frames) // 2, len(frames) - 1}
        for index, frame in enumerate(frames):
            image, _ = CalibrationVisionService.decode_frame(frame.image)
            height, width = image.shape[:2]
            if width > 640:
                reject("No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación.")
            detector.setInputSize((width, height))
            _, faces = detector.detect(image)
            if faces is None or len(faces) != 1 or float(faces[0][14]) < .6:
                reject("Debe verse una sola persona durante toda la comprobación de voz.")
            face = faces[0]
            if index in identity_samples:
                feature = np.asarray(recognizer.feature(recognizer.alignCrop(image, face)), dtype=np.float32).reshape(-1)
                norm = np.linalg.norm(feature)
                from app.services.biometric_service import SFACE_COSINE_THRESHOLD
                if (feature.shape != (128,) or not np.isfinite(feature).all() or norm < 1e-6
                        or float(np.dot(feature / norm, reference)) < SFACE_COSINE_THRESHOLD):
                    reject("El rostro durante la prueba de voz no coincide con tu enrolamiento.")
            eyes = sorted([face[4:6], face[6:8]], key=lambda point: float(point[0]))
            anchors = np.asarray([eyes[0], eyes[1], face[8:10]], dtype=np.float32)
            if float(np.linalg.norm(anchors[1] - anchors[0])) < 12:
                reject("Acercate a la cámara para comprobar el movimiento de la boca.")
            transform = cv2.getAffineTransform(anchors, np.float32([[40, 42], [88, 42], [64, 67]]))
            if not np.isfinite(transform).all():
                reject("No se pudo estabilizar el rostro. Mirá al centro y repetí la comprobación.")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            aligned = cv2.warpAffine(gray, transform, (128, 128), borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            if rectangle is None:
                corners = cv2.transform(np.asarray([[face[10:12], face[12:14]]], dtype=np.float32), transform)[0]
                center = corners.mean(axis=0)
                box_width = float(np.clip(abs(corners[1, 0] - corners[0, 0]) * 1.5, 24, 60))
                box_height = box_width * .7
                x1, x2 = int(center[0] - box_width / 2), int(center[0] + box_width / 2)
                y1, y2 = int(center[1] - box_height / 2), int(center[1] + box_height / 2)
                if not (0 <= x1 < x2 <= 128 and 60 <= y1 < y2 <= 126):
                    reject("No se pudo ubicar la boca con suficiente claridad. Mirá al centro y repetí la comprobación.")
                rectangle = (x1, y1, x2, y2)
            x1, y1, x2, y2 = rectangle
            mouth = aligned[y1:y2, x1:x2]
            cheeks = np.concatenate([aligned[72:108, 16:32].ravel(), aligned[72:108, 96:112].ravel()])
            # Fixed mouth crop and eye/nose alignment reduce whole-head motion;
            # cheek differences compensate some camera/exposure movement, not all.
            mouth = mouth - mouth.mean()
            cheeks = cheeks - cheeks.mean()
            if previous is not None:
                prior_time, prior_mouth, prior_cheeks = previous
                movement = max(0.0, float(np.mean(np.abs(mouth - prior_mouth))
                                         - np.mean(np.abs(cheeks - prior_cheeks))) / 255)
                trace.append(((frame.time_ms / 1000 + prior_time) / 2, movement))
            previous = (frame.time_ms / 1000, mouth, cheeks)
        return trace

    @classmethod
    def assess(cls, frames, audio, enrollment):
        duration = len(audio) / 16000
        times = np.asarray([frame.time_ms / 1000 for frame in frames], dtype=np.float64)
        if (not 20 <= len(frames) <= 100 or not 7 <= duration <= 10 or not np.isfinite(times).all()
                or times[0] < 0 or times[0] > .25 or times[-1] < duration - .3
                or times[-1] > duration + .1 or np.any(np.diff(times) <= .04)
                or np.max(np.diff(times)) > .35 or np.median(np.diff(times)) > .2):
            reject("No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación.")
        activity = cls.voice_activity(audio)
        pause_flags = [bool(voiced) for time, voiced in activity if time >= 4.5]
        run = maximum = 0
        for voiced in pause_flags:
            run = run + 1 if voiced else 0
            maximum = max(maximum, run)
        if sum(pause_flags) >= 5 or maximum >= 3:
            reject("Se detectó voz durante la pausa. Guardá silencio cuando termine la frase y pausá llamadas o conversaciones.")
        if sum(bool(voiced) for time, voiced in activity if time < 4.3) * .03 < .9:
            reject("No se pudo confirmar una sola voz con suficiente evidencia. Repetí la frase con voz clara.")
        trace = cls.mouth_trace(frames, enrollment)
        quiet = np.asarray([motion for time, motion in trace if time >= 4.5])
        if quiet.size < 10:
            reject("No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación.")
        median = float(np.median(quiet))
        threshold = max(.008, median + 3 * float(np.median(np.abs(quiet - median))))
        voiced_motion = [motion > threshold for time, motion in trace
                         if any(voiced and abs(audio_time - time) <= .12 for audio_time, voiced in activity)]
        quiet_ratio = float(np.mean(quiet > threshold))
        if (len(voiced_motion) < 6 or sum(voiced_motion) < 4
                or float(np.mean(voiced_motion)) < max(.35, quiet_ratio + .15)):
            reject("Se detectó voz sin movimiento de boca coincidente. Repetí mirando a cámara y hablando solo cuando se indique.")
        return {"mouth_audio_sync": True, "speech_pause": True}
