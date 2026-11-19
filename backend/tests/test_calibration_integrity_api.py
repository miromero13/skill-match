"""Public no-consumption checks; only visual/model extraction is simulated."""
from types import SimpleNamespace

import numpy as np
import pytest
from tests.test_evaluation_preflight import endpoint, isolated_db, scenario  # noqa: F401
from tests.test_evaluation_calibration import PAYLOAD, prepare
from tests.test_calibration_audio import Detector


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,message", [
    ("multiple", "Se detectaron indicios de más de una voz. Pausá llamadas y conversaciones y repetí la comprobación."),
    ("overlap", "Se detectaron indicios de voces superpuestas. Buscá un ambiente sin conversaciones y repetí la comprobación."),
    ("mouth", "Se detectó voz sin movimiento de boca coincidente. Repetí mirando a cámara y hablando solo cuando se indique."),
    ("pause", "Se detectó voz durante la pausa. Guardá silencio cuando termine la frase y pausá llamadas o conversaciones."),
])
async def test_integrity_rejection_keeps_state_and_quota_and_allows_retry(scenario, monkeypatch, failure, message):
    from app.services.calibration_audio_service import CalibrationAudioService as Audio
    from app.services.calibration_av_service import CalibrationAVService as AV
    from app.services.calibration_speaker_service import CalibrationSpeakerService as Speakers
    from app.services.calibration_vision_service import CalibrationVisionService as Vision
    monkeypatch.setattr(Audio, "detector", staticmethod(lambda: Detector()))
    def speakers(audio):
        if failure == "multiple": return [SimpleNamespace(start=.3, end=1.5, speaker=0), SimpleNamespace(start=2, end=3.5, speaker=1)]
        if failure == "overlap": return [SimpleNamespace(start=.3, end=2, speaker=0), SimpleNamespace(start=1.5, end=3.5, speaker=1)]
        return [SimpleNamespace(start=1, end=3, speaker=0)]
    monkeypatch.setattr(Speakers, "segments", staticmethod(speakers))
    monkeypatch.setattr(AV, "mouth_trace", staticmethod(lambda frames, enrollment: [(i * .1, .04 if failure != "mouth" and 1 <= i * .1 < 3 else 0) for i in range(1, 80)]))
    def assess(frames, audio, label, action, enrollment, ambient, spoken_frames):
        return {"lighting": True, "framing": True, "single_face": True, "identity": True,
                "liveness": True, "passive_screen_check": True, **Audio.assess(ambient, audio),
                **Speakers.assess(np.asarray(audio, dtype=np.float32)), **AV.assess(spoken_frames, audio, enrollment)}
    monkeypatch.setattr(Vision, "assess", assess)
    client, _, _, offer = scenario
    evaluation_id = await prepare(scenario)
    root = f"/api/evaluations/{evaluation_id}"
    challenge = (await client.post(root + "/liveness/challenge")).json()["data"]
    state = (await client.get(root + "/environment/verify")).json()
    quota = (await client.get(endpoint(offer, "preflight"))).json()
    spoken = [0.1 if 16000 <= i < 48000 or (failure == "pause" and 80000 <= i < 96000) else 0 for i in range(128000)]
    body = {**PAYLOAD, "challenge_id": challenge["id"], "audio_samples": spoken}
    rejected = await client.post(root + "/liveness/verify-identity", json=body)
    assert rejected.status_code == 400
    assert rejected.json() == {"statuscode": 400, "message": message, "data": None}
    assert (await client.get(root + "/environment/verify")).json() == state
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
    failure = "none"
    success = await client.post(root + "/liveness/verify-identity", json={**body, "audio_samples": [0.1 if 16000 <= i < 48000 else 0 for i in range(128000)]})
    assert success.status_code == 200
    data = success.json()["data"]
    assert data["ready"] is True and data["started_at"] is None
    assert data["checks"]["single_speaker"] and data["checks"]["mouth_audio_sync"]
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
