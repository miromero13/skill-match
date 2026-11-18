"""Strict local calibration; texture/motion heuristics are not a validated PAD model."""
import base64
import binascii
import hashlib
import json

import cv2
import numpy as np

from app.core.exceptions import SkillMatchException
from app.services.calibration_audio_service import CalibrationAudioService
from app.services.calibration_speaker_service import CalibrationSpeakerService
from app.services.calibration_av_service import CalibrationAVService
from app.services.biometric_service import (
    YUNET_MODEL_PATH, SFACE_MODEL_PATH, SFACE_COSINE_THRESHOLD,
)


def reject(message):
    raise SkillMatchException(statuscode=400, message=message)


class CalibrationVisionService:
    @staticmethod
    def decode_frame(raw):
        encoded = raw.split(",", 1)[1] if raw.startswith("data:image/jpeg;base64,") else raw
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            reject("La captura de calibración no es una imagen JPEG válida.")
        # Read JPEG dimensions before decompression to reject oversized images.
        if data[:2] != b"\xff\xd8":
            reject("La captura de calibración no es una imagen JPEG válida.")
        pos, dimensions = 2, None
        while pos + 3 < len(data):
            if data[pos] != 0xFF:
                break
            while pos < len(data) and data[pos] == 0xFF:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]
            pos += 1
            if marker in (0xDA, 0xD9):
                break
            size = int.from_bytes(data[pos:pos + 2], "big")
            if size < 2 or pos + size > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2) and size >= 7:
                dimensions = (int.from_bytes(data[pos + 5:pos + 7], "big"),
                              int.from_bytes(data[pos + 3:pos + 5], "big"))
                break
            pos += size
        if dimensions is None or not (320 <= dimensions[0] <= 1280 and 240 <= dimensions[1] <= 960):
            reject("La cámara debe entregar imágenes JPEG entre 320×240 y 1280×960.")
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or (image.shape[1], image.shape[0]) != dimensions:
            reject("La captura de calibración no se pudo decodificar.")
        return image, hashlib.sha256(data).digest()

    @staticmethod
    def models():
        if not YUNET_MODEL_PATH.is_file() or not SFACE_MODEL_PATH.is_file():
            raise SkillMatchException(statuscode=503, message="Los modelos locales de calibración no están disponibles.")
        try:
            # Per-request instances avoid mutating the shared profile detector.
            detector = cv2.FaceDetectorYN.create(str(YUNET_MODEL_PATH), "", (640, 480), 0.6, 0.3, 5)
            recognizer = cv2.FaceRecognizerSF.create(str(SFACE_MODEL_PATH), "")
            return detector, recognizer
        except cv2.error as exc:
            raise SkillMatchException(statuscode=503, message="No se pudieron cargar los modelos locales de calibración.") from exc

    @staticmethod
    def passive_screen_check(gray):
        # Experimental periodic-texture indicator. It cannot rule out replay/deepfake.
        gray = cv2.resize(gray, (96, 96)).astype(np.float32)
        spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray - gray.mean()))) ** 2
        spectrum[40:57, 40:57] = 0
        energy = float(spectrum.sum())
        return energy == 0 or float(spectrum.max()) / energy < 0.16

    @classmethod
    def assess(cls, frames, audio_samples, camera_label, action, enrollment, ambient_audio_samples=None, spoken_frames=None):
        decoded = [cls.decode_frame(raw) for raw in frames]
        if len({digest for _, digest in decoded}) < 3:
            reject("La prueba de vida requiere una secuencia de imágenes diferentes.")
        label = camera_label.casefold()
        if any(name in label for name in ("obs", "manycam", "v4l2loopback", "virtual cam")):
            reject("Seleccioná una cámara física para la calibración.")
        try:
            reference = np.asarray(json.loads(enrollment), dtype=np.float32)
        except (ValueError, TypeError):
            reject("Tu referencia biométrica no es válida. Volvé a registrar tu rostro.")
        if reference.shape != (128,) or not np.isfinite(reference).all() or np.linalg.norm(reference) < 1e-6:
            reject("Tu referencia biométrica no es válida. Volvé a registrar tu rostro.")
        reference /= np.linalg.norm(reference)
        detector, recognizer = cls.models()
        poses = []
        for image, _ in decoded:
            height, width = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            brightness = float(gray.mean()) / 255
            if brightness < 0.15 or brightness > 0.98:
                reject("Iluminación insuficiente o excesiva. Ajustá la luz del ambiente y repetí la comprobación.")
            detector.setInputSize((width, height))
            _, faces = detector.detect(image)
            if faces is None or len(faces) != 1:
                reject("Debe verse una sola persona durante toda la calibración.")
            face = faces[0]
            x, y, fw, fh = map(float, face[:4])
            if (float(face[14]) < 0.6 or abs(x + fw / 2 - width / 2) / width > 0.28
                    or abs(y + fh / 2 - height / 2) / height > 0.32
                    or fw / width < 0.12 or fh / height < 0.14):
                reject("Ubicá tu rostro dentro del encuadre y acercate a la cámara.")
            x1, y1 = max(0, int(x)), max(0, int(y))
            crop = gray[y1:min(height, int(y + fh)), x1:min(width, int(x + fw))]
            if crop.size == 0 or float(cv2.Laplacian(crop, cv2.CV_64F).var()) < 10:
                reject("La imagen está desenfocada. Ajustá la cámara y repetí la comprobación.")
            if not cls.passive_screen_check(crop):
                reject("Se detectaron patrones de imagen sospechosos. Evitá pantallas frente a la cámara y repetí la comprobación.")
            aligned = recognizer.alignCrop(image, face)
            feature = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(feature))
            if feature.shape != (128,) or not np.isfinite(feature).all() or norm < 1e-6:
                reject("No se pudo extraer un rostro válido para la calibración.")
            if float(np.dot(feature / norm, reference)) < SFACE_COSINE_THRESHOLD:
                reject("El rostro de la cámara no coincide con tu enrolamiento.")
            eye_mid = (float(face[4]) + float(face[6])) / 2
            eye_distance = abs(float(face[6]) - float(face[4]))
            if eye_distance < 1:
                reject("No se pudo verificar la posición del rostro.")
            poses.append((float(face[8]) - eye_mid) / eye_distance)
        direction = -1 if action == "TURN_LEFT" else 1
        if (abs(poses[0]) > 0.18 or abs(poses[-1] - poses[0]) > 0.09
                or not any(direction * (pose - poses[0]) >= 0.12 for pose in poses[1:-1])):
            reject("No se completó el movimiento solicitado. Mirá al centro, girá hacia el lado indicado y volvé al centro.")
        audio_checks = CalibrationAudioService.assess(ambient_audio_samples, audio_samples)
        speaker_checks = CalibrationSpeakerService.assess(np.asarray(audio_samples, dtype=np.float32))
        av_checks = CalibrationAVService.assess(spoken_frames or [], audio_samples, enrollment)
        return {"lighting": True, "framing": True, "single_face": True,
                "identity": True, "liveness": True, "passive_screen_check": True,
                **audio_checks, **speaker_checks, **av_checks}
