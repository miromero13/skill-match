"""Public no-consumption checks; only visual/model extraction is simulated (the engine runs for real).

Rewritten in T9: the old test stubbed the four ``Calibration*Service`` classes one by one; the same four rejections and
messages are produced here by the real engine over a faked frame boundary, and a repeat with the same challenge succeeds.
"""
import pytest

from tests.test_evaluation_preflight import endpoint, isolated_db, scenario  # noqa: F401
from tests.test_calibration_audio import consented
from audio_fixtures import Segment, SR, voice
from integrity_fixtures import face_b64  # noqa: F401
from test_calibration_audiovisual import set_mouth
from test_integrity_calibration import AMBIENT_MS, http_body
from app.services.integrity import messages as m


def break_it(good, failure):
    """Returns the audio to send for ``failure`` after breaking the corresponding part of the calibration."""
    audio = good.audio.copy()
    if failure == "multiple":
        good.segments = lambda a: [Segment(0.3, 1.5, 0), Segment(2, 3.5, 1)]
    elif failure == "overlap":
        good.segments = lambda a: [Segment(0.3, 2, 0), Segment(1.5, 3.5, 1)]
    elif failure == "mouth":
        set_mouth(good, lambda t: 0.05)
    elif failure == "pause":
        start = (AMBIENT_MS + 5000) * SR // 1000
        audio[start:start + SR] = voice(1.0)
    return audio


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,message", [
    ("multiple", m.MORE_THAN_ONE_VOICE),
    ("overlap", m.OVERLAPPING_VOICES),
    ("mouth", m.VOICE_WITHOUT_MOUTH),
    ("pause", m.SPEECH_DURING_PAUSE),
])
async def test_integrity_rejection_keeps_state_and_quota_and_allows_retry(scenario, monkeypatch, failure, message):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    state = (await client.get(root + "/environment/verify")).json()
    quota = (await client.get(endpoint(offer, "preflight"))).json()
    original = http_body(good, challenge["id"])
    rejected = await client.post(root + "/liveness/verify-identity",
                                 json={**http_body(good, challenge["id"], break_it(good, failure))})
    assert rejected.status_code == 400
    assert rejected.json() == {"statuscode": 400, "message": message, "data": None}
    assert (await client.get(root + "/environment/verify")).json() == state
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
    # Repeating with the same challenge after fixing the problem succeeds: a rejection consumes nothing.
    fixed = [Segment(0.0, 8.0, 0)]
    good.segments = lambda a: fixed
    good.reset_mouth()
    success = await client.post(root + "/liveness/verify-identity", json=original)
    assert success.status_code == 200
    data = success.json()["data"]
    assert data["ready"] is True and data["started_at"] is None
    assert data["checks"]["single_speaker"] and data["checks"]["mouth_audio_sync"]
    assert (await client.get(endpoint(offer, "preflight"))).json() == quota
