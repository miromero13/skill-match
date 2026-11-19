"""Public calibration contract and local voice-activity policy (no application DB)."""
import numpy as np
import pytest

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401

QUIET = [0.0] * 48000
VOICE = [0.1] * 128000
SPOKEN_QUIET = [0.0] * 128000
BACKGROUND_VOICE = [0.001] * 48000
NOISE = [0.03] * 48000


class Detector:
    def is_speech(self, pcm, rate):
        assert rate == 16000 and len(pcm) == 960
        value = abs(int(np.frombuffer(pcm, dtype="<i2")[0]))
        return 20 <= value <= 40 or value >= 3000


@pytest.mark.parametrize("background,spoken,message", [
    (BACKGROUND_VOICE, VOICE, "Se detectó voz durante el silencio. Pausá llamadas, videos o conversaciones y repetí la comprobación."),
    (NOISE, VOICE, "Hay demasiado ruido de fondo. Buscá un ambiente más silencioso y repetí la comprobación."),
    (QUIET, SPOKEN_QUIET, "No se detectó voz suficiente. Decí «Estoy listo para comenzar» cuando se indique y repetí la comprobación."),
])
def test_separate_background_and_spoken_windows(background, spoken, message, monkeypatch):
    from app.services.calibration_audio_service import CalibrationAudioService
    from app.core.exceptions import SkillMatchException
    monkeypatch.setattr(CalibrationAudioService, "detector", staticmethod(lambda: Detector()))
    with pytest.raises(SkillMatchException) as caught:
        CalibrationAudioService.assess(background, spoken)
    assert caught.value.statuscode == 400 and caught.value.message == message


def test_quiet_then_voice_is_required_and_silence_is_not_approved(monkeypatch):
    from app.services.calibration_audio_service import CalibrationAudioService
    monkeypatch.setattr(CalibrationAudioService, "detector", staticmethod(lambda: Detector()))
    assert CalibrationAudioService.assess(QUIET, VOICE) == {"microphone": True, "background_quiet": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("background,spoken,message", [
    (BACKGROUND_VOICE, VOICE, "Se detectó voz durante el silencio. Pausá llamadas, videos o conversaciones y repetí la comprobación."),
    (NOISE, VOICE, "Hay demasiado ruido de fondo. Buscá un ambiente más silencioso y repetí la comprobación."),
    (QUIET, SPOKEN_QUIET, "No se detectó voz suficiente. Decí «Estoy listo para comenzar» cuando se indique y repetí la comprobación."),
])
async def test_audio_rejection_preserves_public_state_and_quota(scenario, monkeypatch, background, spoken, message):
    from app.services.calibration_audio_service import CalibrationAudioService
    from app.services.calibration_vision_service import CalibrationVisionService
    monkeypatch.setattr(CalibrationAudioService, "detector", staticmethod(lambda: Detector()))
    def assess(frames, audio, label, action, enrollment, ambient, spoken_frames):
        return {"lighting": True, "framing": True, "single_face": True, "identity": True,
                "liveness": True, "passive_screen_check": True, "single_speaker": True, "no_overlap": True,
                "mouth_audio_sync": True, "speech_pause": True, **CalibrationAudioService.assess(ambient, audio)}
    monkeypatch.setattr(CalibrationVisionService, "assess", assess)
    client, _, _, offer = scenario
    consent = await client.post(endpoint(offer, "consent"), json=CONSENT)
    evaluation_id = consent.json()["data"]["id"]
    root = f"/api/evaluations/{evaluation_id}"
    challenge = (await client.post(root + "/liveness/challenge")).json()["data"]
    state = (await client.get(root + "/environment/verify")).json()
    quota = (await client.get(endpoint(offer, "preflight"))).json()
    payload = {"challenge_id": challenge["id"], "frames": ["a", "b", "c"],
               "audio_samples": spoken, "ambient_audio_samples": background, "camera_label": "Physical webcam",
               "spoken_frames": [{"time_ms": i * 100, "image": "mock-jpeg"} for i in range(80)]}
    rejected = await client.post(root + "/liveness/verify-identity", json=payload)
    assert rejected.status_code == 400
    assert rejected.json() == {"statuscode": 400, "message": message, "data": None}
    assert (await client.get(root + "/environment/verify")).json() == state
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
    # A rejected check does not consume the challenge or exam attempt.
    success = await client.post(root + "/liveness/verify-identity", json={**payload, "audio_samples": VOICE, "ambient_audio_samples": QUIET})
    assert success.status_code == 200
    assert success.json()["data"]["ready"] is True
    assert success.json()["data"]["started_at"] is None
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
