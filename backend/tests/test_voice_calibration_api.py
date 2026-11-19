"""T8 / S3, S4, S11: POST /api/browser-supervision/trials/{id}/voice-calibration enrolls the trial's voiceprint.

The speaker models are replaced by level-based fakes (see audio_fixtures); the rules under test are the endpoint's:
lease and 404 policy, the three-phase off-loop pattern, the rejections and that the embedding never leaves the server.
"""
import json
import threading
import uuid
from pathlib import Path

import numpy as np
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, update

from app.core.security import create_access_token
from app.models import User, UserRole
from app.models.browser_supervision import BrowserTrial
from app.services import browser_supervision_service as service
from app.services.continuous_supervision_service import ContinuousSupervisionService as Service
from app.services.integrity import audio_analyzer
from app.services.integrity import voiceprint as vp
from app.services.integrity.models import FrameBatch, FrameObservation
from audio_fixtures import LevelExtractor, Segment, SR, install_fake_vad, mouth_samples, silence, speaking, syllables
from test_av_missing_evidence import window  # noqa: F401
from test_browser_supervision import LOCKED, ROOT, body  # noqa: F401
from test_continuous_supervision import start_trial  # noqa: F401
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401

SAVED = "Voz calibrada."
AMBIENT_MS = 1000
PHRASE_S = 4.0


def one_voice(audio):
    return [Segment(0.0, len(audio) / SR, 0)]


class ServerFrames:
    """The server's own measurement of the sampled frames: ``"mouth:<aperture>"`` is a face with that aperture."""

    def __init__(self):
        self.faces, self.unavailable = 1, False

    def analyze_frames(self, frames, reference, session_key, times_ms=None):
        if self.unavailable:
            return FrameBatch(model_unavailable=True)
        usable = [(i, raw) for i, raw in enumerate(frames) if raw.startswith("mouth:")]
        observed = tuple(FrameObservation(face_count=self.faces, mouth_open_score=float(raw[6:]), blendshapes={"jawOpen": 0.0})
                         for _, raw in usable)
        times = tuple(int(times_ms[i]) for i, _ in usable) if times_ms is not None and len(usable) == len(frames) else ()
        return FrameBatch(frames=observed, video_missing=not usable, times_ms=times)


@pytest.fixture
def models(monkeypatch):
    """The speaker models: diarization finds one voice (``segments``), the extractor tells voices by loudness.
    The vision models are replaced by ``ServerFrames`` (state["frames"])."""
    install_fake_vad(monkeypatch)
    state = {"segments": one_voice, "extractor": LevelExtractor(), "frames": ServerFrames()}
    monkeypatch.setattr(Service, "_frame_analyzer", classmethod(lambda cls, use_mediapipe=True: state["frames"]))
    monkeypatch.setattr(audio_analyzer, "_default_segments", lambda audio: state["segments"](audio))
    monkeypatch.setattr(vp, "default_extractor", lambda: state["extractor"])
    return state


def recording(speaker=1, phrase_s=PHRASE_S, still=False, mouth=True, ambient=None, env_seed=3):
    chunks = int(phrase_s * 1000 / 30)
    env = syllables(env_seed, chunks=chunks)
    audio = np.concatenate([silence(AMBIENT_MS / 1000) if ambient is None else ambient, speaking(env, speaker)])
    readings = [{"t_ms": s.t_ms + AMBIENT_MS, "mouth_open": s.mouth_open} for s in mouth_samples(env, still=still)]
    return audio, (readings if mouth else [])


def sampled(audio, readings=None, step_ms=66):
    """Frames sampled while recording: they show the aperture of ``readings`` (or a still mouth without any)."""
    if readings:
        return [{"t_ms": r["t_ms"], "image": f"mouth:{r['mouth_open']}"} for r in readings]
    return [{"t_ms": at, "image": "mouth:0.05"} for at in range(0, len(audio) * 1000 // SR - step_ms, step_ms)]


def payload(tab, audio=None, mouth=None, **kw):
    if audio is None:
        audio, mouth = recording()
    frames = kw.pop("frames", None)
    return {"tab_id": tab, "audio_samples": [float(v) for v in audio], "ambient_ms": AMBIENT_MS,
            "mouth_samples": mouth or [], "frames": sampled(audio, mouth) if frames is None else frames, **kw}


async def enroll(client, trial, body_):
    return await client.post(f"{ROOT}/{trial['id']}/voice-calibration", json=body_)


async def stored(db, trial):
    db.expire_all()
    return (await db.execute(select(BrowserTrial.voiceprint).where(BrowserTrial.id == uuid.UUID(trial["id"])))
            ).scalar_one()


@pytest.mark.asyncio
async def test_enrollment_stores_the_voiceprint_and_never_returns_it(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    assert trial["voice_enrolled"] is False
    response = await enroll(client, trial, payload(tab))
    assert response.status_code == 200 and response.json()["message"] == SAVED
    data = response.json()["data"]
    assert data["voice_enrolled"] is True and data["voiced_seconds"] >= 3.0
    record = await stored(db, trial)
    assert len(record["embedding"]) == 16 and record["ambient_rms"] < 0.001
    assert "embedding" not in response.text and "voiceprint" not in response.text
    reread = await client.get(f"{ROOT}/{trial['id']}")
    assert reread.json()["data"]["voice_enrolled"] is True
    assert "embedding" not in reread.text and "voiceprint" not in reread.text
    assert "embedding" not in json.dumps((await client.get(f"{ROOT}/{trial['id']}/events")).json())


@pytest.mark.asyncio
async def test_the_ambient_floor_is_measured_from_the_silence_segment(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    hiss = (0.01 * np.random.default_rng(1).normal(0, 1, SR)).astype(np.float32)  # a noisy room, no speech
    audio, mouth = recording(ambient=hiss)
    assert (await enroll(client, trial, payload(tab, audio, mouth))).status_code == 200
    assert 0.005 < (await stored(db, trial))["ambient_rms"] < 0.02


@pytest.mark.asyncio
async def test_recalibration_replaces_the_voiceprint(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    await enroll(client, trial, payload(tab))
    first = (await stored(db, trial))["embedding"]
    audio, mouth = recording(speaker=2)
    assert (await enroll(client, trial, payload(tab, audio, mouth))).status_code == 200
    assert (await stored(db, trial))["embedding"] != first


REJECTIONS = {
    "little": (lambda: recording(phrase_s=2.0), 400,
               "No escuchamos suficiente voz. Leé la frase completa en voz alta y repetí la calibración."),
    "unsynced": (lambda: recording(still=True), 400,
                 "Tu voz no coincide con el movimiento de tus labios. Mirá la cámara, leé la frase en voz alta y "
                 "repetí la calibración."),
    "nomouth": (lambda: recording(mouth=False), 400,
                "No pudimos ver el movimiento de tu boca. Ubicate frente a la cámara con la boca descubierta y "
                "repetí la calibración."),
    "ambient": (lambda: recording(ambient=speaking(syllables(9, chunks=33), 1)), 400,
                "Había voces o ruido durante el silencio inicial. Buscá un ambiente en silencio y repetí la "
                "calibración."),
}


@pytest.mark.parametrize("case", sorted(REJECTIONS))
@pytest.mark.asyncio
async def test_unusable_recordings_are_a_400_in_spanish_and_store_nothing(scenario, models, case):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    build, status, message = REJECTIONS[case]
    audio, mouth = build()
    response = await enroll(client, trial, payload(tab, audio, mouth))
    assert response.status_code == status and response.json() == body(message, status=status)
    assert await stored(db, trial) is None
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["voice_enrolled"] is False


@pytest.mark.asyncio
async def test_several_speakers_are_rejected(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    models["segments"] = lambda audio: [Segment(0.0, 2.0, 0), Segment(2.0, 4.0, 1)]
    response = await enroll(client, trial, payload(tab))
    assert response.status_code == 400
    assert response.json() == body("Se detectó más de una voz durante la calibración. Tiene que hablar solo vos, sin "
                                   "otras personas ni audio reproducido, y repetí la calibración.", status=400)
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_segments_that_are_not_one_voice_are_rejected(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    chunks = int(PHRASE_S * 1000 / 30)
    env = syllables(3, chunks=chunks)
    halves = np.concatenate([speaking(env[: chunks // 2], 1), speaking(env[chunks // 2:], 2)])
    audio = np.concatenate([silence(AMBIENT_MS / 1000), halves])
    mouth = [{"t_ms": s.t_ms + AMBIENT_MS, "mouth_open": s.mouth_open} for s in mouth_samples(env)]
    response = await enroll(client, trial, payload(tab, audio, mouth))
    assert response.status_code == 400
    assert response.json() == body("No pudimos confirmar una sola voz constante. Repetí la frase en un ambiente "
                                   "silencioso.", status=400)
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_a_missing_speaker_model_is_a_503_not_an_enrollment(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    models["extractor"].fail = vp.SpeakerModelUnavailable("missing")
    response = await enroll(client, trial, payload(tab))
    assert response.status_code == 503
    assert response.json() == body("La verificación de voz no está disponible en este momento. Reintentá más tarde.",
                                   status=503)
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_the_diarization_model_missing_is_also_a_503(scenario, models):
    client, db, _, _ = scenario

    def broken(_audio):
        raise RuntimeError("no models")

    models["segments"] = broken
    trial, tab = await start_trial(client)
    assert (await enroll(client, trial, payload(tab))).status_code == 503
    assert await stored(db, trial) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(audio_samples=[0.0] * 192_001),  # over 12 s
        lambda p: p.update(audio_samples=[]),
        lambda p: p.update(ambient_ms=100),
        lambda p: p.update(ambient_ms=3500),
        lambda p: p.update(mouth_samples=[{"t_ms": 0, "mouth_open": 0.1}, {"t_ms": 10, "mouth_open": 0.1}]),
        lambda p: p.update(mouth_samples=[{"t_ms": 0, "mouth_open": 5.0}]),
        lambda p: p.update(mouth_samples=[{"t_ms": 0, "mouth_open": 0.1, "extra": 1}]),
        lambda p: p.update(extra=1),
        lambda p: p.pop("frames"),  # no server frames: the telemetry could not be verified
        lambda p: p.update(frames=p["frames"][:19]),
        lambda p: p.update(frames=p["frames"] * 3),
        lambda p: p.update(frames=[{**p["frames"][0], "image": "m" * 80_001}, *p["frames"][1:]]),
        lambda p: p.update(frames=[{**p["frames"][0], "t_ms": 12_001}, *p["frames"][1:]]),
        lambda p: p.update(frames=[{**p["frames"][0], "extra": 1}, *p["frames"][1:]]),
        lambda p: p.update(frames=list(reversed(p["frames"]))),
        lambda p: p.update(frames=[{"t_ms": i * 10, "image": "mouth:0.1"} for i in range(30)]),
    ],
)
@pytest.mark.asyncio
async def test_invalid_payload_is_a_422_envelope(scenario, models, mutate):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    data = payload(tab)
    mutate(data)
    response = await enroll(client, trial, data)
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_foreign_members_and_admins_get_the_404_and_other_tabs_the_lease_conflict(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    conflict = await enroll(client, trial, payload(str(uuid.uuid4())))
    assert conflict.status_code == 409 and conflict.json() == body(LOCKED, status=409)
    original = client.headers["Authorization"]
    for role in (UserRole.MEMBER, UserRole.ADMIN):
        other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=role)
        db.add(other)
        await db.commit()
        client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role=role.value)}"
        response = await enroll(client, trial, payload(tab))
        assert response.status_code == 404 and response.json() == body("Recurso no encontrado", status=404)
    client.headers["Authorization"] = original
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_inference_runs_off_the_event_loop_and_the_lease_is_rechecked_before_storing(scenario, models, monkeypatch):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    import asyncio

    seen = {}
    real = Service.enroll_voice
    loop = asyncio.get_running_loop()

    def spy(*args, **kwargs):
        seen["thread"] = threading.current_thread()
        # The lease is lost while the (slow) inference runs: nothing may be stored afterwards. The loop is free
        # to serve this because the inference does not block it.
        asyncio.run_coroutine_threadsafe(_expire(trial), loop).result(timeout=10)
        return real(*args, **kwargs)

    async def _expire(current):
        await db.execute(update(BrowserTrial).where(BrowserTrial.id == uuid.UUID(current["id"]))
                         .values(tab_id=uuid.uuid4()))
        await db.commit()

    monkeypatch.setattr(Service, "enroll_voice", staticmethod(spy))
    response = await enroll(client, trial, payload(tab))
    assert seen["thread"] is not threading.main_thread()
    assert response.status_code == 409 and response.json() == body(LOCKED, status=409)
    assert await stored(db, trial) is None


# ---- the voiceprint reaches the supervision windows ---------------------------------------------

@pytest.mark.asyncio
async def test_windows_receive_the_voiceprint_and_report_voice_and_lip_sync(scenario, models, monkeypatch):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"face_count": 1, "head_orientation": "CENTER", "identity_match": None, "speech_detected": True,
                "mouth_moving": True, "mouth_sync": True, "multiple_speakers": False, "noise_level": 0.0,
                "anomalies": [], "voice_match": True, "lip_sync": "synced"}

    monkeypatch.setattr(Service, "assess_window", staticmethod(fake))
    first = await client.post(f"{ROOT}/{trial['id']}/av-window", json=window(tab))
    assert calls[0]["voiceprint"] is None
    assert first.json()["data"]["voice_match"] is True and first.json()["data"]["lip_sync"] == "synced"
    await enroll(client, trial, payload(tab))
    await client.post(f"{ROOT}/{trial['id']}/av-window", json=window(tab))
    assert len(calls[1]["voiceprint"]["embedding"]) == 16


@pytest.mark.asyncio
async def test_window_response_fields_default_to_null(scenario, models, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    monkeypatch.setattr(Service, "assess_window", staticmethod(lambda **_k: {
        "face_count": 1, "head_orientation": "CENTER", "identity_match": None, "speech_detected": False,
        "mouth_moving": False, "mouth_sync": None, "multiple_speakers": False, "noise_level": 0.0, "anomalies": []}))
    data = (await client.post(f"{ROOT}/{trial['id']}/av-window", json=window(tab))).json()["data"]
    assert data["voice_match"] is None and data["lip_sync"] is None


@pytest.mark.asyncio
async def test_new_kinds_are_accepted_in_the_ledger_only_from_the_server_side(scenario, models):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    event = {"event_id": str(uuid.uuid4()), "kind": "VOICE_MISMATCH", "observed_at": "2026-01-01T00:00:00+00:00",
             "duration_ms": 0}
    # They are valid kinds (the schema lists them) but count against the audiovisual cap, not the browser one.
    response = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": tab, "events": [event]})
    assert response.status_code == 200
    assert "VOICE_MISMATCH" in service.AV_KINDS


def test_alembic_has_a_single_head_and_the_voiceprint_sits_on_top_of_the_gaze_zone():
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1
    head = script.get_revision(script.get_heads()[0])
    assert head.revision == "f3a8d2c19e47" and head.down_revision == "e5b1c7d3a962"  # T9: calibration inputs on top
    assert script.get_revision(head.down_revision).down_revision == "c4e8a1f27b95"


# ---- T9b: the server frames cross-check the mouth telemetry (CLIENT_MISMATCH mechanism) ----------------------------


def message(code):
    from app.services.integrity import messages
    return messages.VOICE_CALIBRATION_ERRORS[code]


@pytest.mark.asyncio
async def test_telemetry_the_server_frames_contradict_rejects_the_enrollment(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    audio, mouth = recording()
    lying = [{**r, "mouth_open": r["mouth_open"] + 0.6} for r in mouth]  # the browser claims much wider openings
    response = await enroll(client, trial, payload(tab, audio, lying, frames=sampled(audio, mouth)))
    status, text = message("UNTRUSTED_TELEMETRY")
    assert response.status_code == status and response.json() == body(text, status=status)
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_frames_that_never_coincide_with_the_telemetry_reject_the_enrollment(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    audio, mouth = recording()
    early, late = mouth[:20], [r for r in mouth if r["t_ms"] >= 3000]  # the telemetry ends before the frames begin
    response = await enroll(client, trial, payload(tab, audio, early, frames=sampled(audio, late)))
    assert response.status_code == 400 and response.json()["message"] == message("UNTRUSTED_TELEMETRY")[1]
    assert await stored(db, trial) is None


@pytest.mark.parametrize("setup,code", [
    (lambda frames: setattr(frames, "faces", 2), "MULTIPLE_FACES"),
    (lambda frames: setattr(frames, "faces", 0), "NO_FACE"),
])
@pytest.mark.asyncio
async def test_a_second_person_or_nobody_in_the_frames_rejects_the_enrollment(scenario, models, setup, code):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    setup(models["frames"])
    response = await enroll(client, trial, payload(tab))
    status, text = message(code)
    assert response.status_code == status and response.json() == body(text, status=status)
    assert await stored(db, trial) is None


@pytest.mark.asyncio
async def test_undecodable_frames_and_missing_vision_models_fail_closed(scenario, models):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    audio, mouth = recording()
    frames = sampled(audio, mouth)
    frames[3] = {**frames[3], "image": "garbage"}
    response = await enroll(client, trial, payload(tab, audio, mouth, frames=frames))
    assert response.status_code == 400 and response.json()["message"] == message("NO_VIDEO")[1]
    models["frames"].unavailable = True
    response = await enroll(client, trial, payload(tab, audio, mouth))
    status, text = message("VISION_UNAVAILABLE")
    assert response.status_code == 503 == status and response.json() == body(text, status=503)
    assert await stored(db, trial) is None
