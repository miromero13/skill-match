"""Public calibration contract and the silence/speech policy through the engine (no application DB).

Rewritten in T9: ``CalibrationAudioService`` and its ``detector`` seam no longer exist; the same rejections and
messages are asserted on ``CalibrationProfile.ambient`` / ``speech`` over the shared ``AudioAnalyzer`` (fake VAD) and,
over HTTP, on the real engine with only the frame boundary faked.
"""
import numpy as np
import pytest

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401
from app.services.integrity import messages as m, thresholds as t
from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.calibration import CalibrationProfile
from app.services.integrity.state import InMemoryStateStore
from audio_fixtures import LevelExtractor, Segment, SR, install_fake_vad, silence, voice
from test_integrity_calibration import AMBIENT_MS, Calibration, http_body, replace_audio, valid_reference

NOISE = np.full(AMBIENT_MS * SR // 1000, 0.03, dtype=np.float32)
VOICE_IN_SILENCE = np.concatenate([silence(0.5), voice(1.0), silence(0.5)])


def analyze(monkeypatch, samples):
    install_fake_vad(monkeypatch)
    analyzer = AudioAnalyzer(InMemoryStateStore(), speaker_segments=lambda a: [Segment(0.0, len(a) / SR, 0)],
                             extractor=LevelExtractor(), vad_floor=0.0, min_speaker_s=t.CAL_SPEAKER_MIN_DURATION_S)
    return analyzer.analyze(samples)


@pytest.mark.parametrize("background,message", [
    (VOICE_IN_SILENCE, m.SPEECH_DURING_SILENCE),
    (NOISE, m.BACKGROUND_NOISE),
])
def test_silence_step_rejects_voice_and_noise(monkeypatch, background, message):
    failed = [c for c in CalibrationProfile().ambient(analyze(monkeypatch, background), background) if not c.passed]
    assert [(c.name, c.reason, c.status) for c in failed] == [("background_quiet", message, 400)]


def test_speech_step_needs_voice_and_silence_alone_is_not_approved(monkeypatch):
    spoken = np.zeros(128000, dtype=np.float32)
    failed = [c for c in CalibrationProfile().speech(analyze(monkeypatch, spoken), spoken) if not c.passed]
    assert [(c.name, c.reason) for c in failed] == [("microphone", m.NOT_ENOUGH_SPEECH)]


def test_quiet_then_voice_passes_both_steps(monkeypatch):
    quiet = silence(2.0)
    assert all(c.passed for c in CalibrationProfile().ambient(analyze(monkeypatch, quiet), quiet))
    spoken = np.concatenate([voice(3.0), silence(5.0)])
    assert all(c.passed for c in CalibrationProfile().speech(analyze(monkeypatch, spoken), spoken))


def test_an_unavailable_vad_is_503_never_silence(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "webrtcvad", None)
    audio = AudioAnalyzer(InMemoryStateStore(), extractor=LevelExtractor(), vad_floor=0.0).analyze(silence(2.0))
    failed = [c for c in CalibrationProfile().ambient(audio, silence(2.0)) if not c.passed]
    assert [(c.name, c.status, c.reason) for c in failed] == [("background_quiet", 503, m.VAD_UNAVAILABLE)]


async def consented(scenario, monkeypatch):
    """A consented evaluation, its challenge and a calibration whose engine replaces the vision service's."""
    import json
    from app.services.calibration_vision_service import CalibrationVisionService
    client, db, user, offer = scenario
    user.biometric_embedding = valid_reference()
    await db.commit()
    evaluation_id = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    root = f"/api/evaluations/{evaluation_id}"
    challenge = (await client.post(root + "/liveness/challenge")).json()["data"]
    good = Calibration(monkeypatch, challenge["action"])
    monkeypatch.setattr(CalibrationVisionService, "engine", staticmethod(good.engine))
    return client, offer, root, challenge, good


@pytest.mark.asyncio
@pytest.mark.parametrize("change,message", [
    (lambda good: replace_audio(good, ambient=VOICE_IN_SILENCE), m.SPEECH_DURING_SILENCE),
    (lambda good: replace_audio(good, ambient=NOISE), m.BACKGROUND_NOISE),
    (lambda good: np.concatenate([silence(AMBIENT_MS / 1000), silence(8.0)]), m.NOT_ENOUGH_SPEECH),
])
async def test_audio_rejection_preserves_public_state_and_quota(scenario, monkeypatch, change, message):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    state = (await client.get(root + "/environment/verify")).json()
    quota = (await client.get(endpoint(offer, "preflight"))).json()
    rejected = await client.post(root + "/liveness/verify-identity",
                                 json=http_body(good, challenge["id"], np.asarray(change(good), dtype=np.float32)))
    assert rejected.status_code == 400
    assert rejected.json() == {"statuscode": 400, "message": message, "data": None}
    assert (await client.get(root + "/environment/verify")).json() == state
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
    # A rejected check does not consume the challenge or exam attempt.
    success = await client.post(root + "/liveness/verify-identity", json=http_body(good, challenge["id"]))
    assert success.status_code == 200
    assert success.json()["data"]["ready"] is True
    assert success.json()["data"]["started_at"] is None
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
