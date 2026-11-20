"""Flute song mode (S2, S4, S5, S6): song catalog, per-note scoring and endpoints."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.ai.datasets import router as dataset_router
from app.core.deps import get_current_admin_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.main import app
from app.services import flute_song_service as songs
from app.services import flute_training_service as fts

HIMNO = songs.FLUTE_SONGS["himno_alegria"]
FRAME_S = 0.025  # 40 Hz pitch track
HAND_S = 0.1  # 10 Hz audio/hand frames
# Fake finger head: holes 1-3 read from the left slot, holes 4-7 from the right slot.
HOLE_IDX = (2, 3, 4, 27, 28, 29, 30)
REPEATED = {1, 4, 9, 12, 14, 16, 19, 24, 29}
DO_NOTES = {8, 9, 23, 24, 28, 29}


# --------------------------------------------------------------------------- #
# Synthetic performances
# --------------------------------------------------------------------------- #
def performance(bpm=120, shift=0.0, played=None, late=None, dips=True, silent=False, cents=0.0):
    """40 Hz pitch track of the song: `played` replaces notes, `late` delays onsets (s)."""
    played, late = played or {}, late or {}
    spb = 60.0 / bpm
    notes = HIMNO["notes"]
    starts = [n["start_beats"] * spb + late.get(n["index"], 0.0) + shift for n in notes]
    end = (notes[-1]["start_beats"] + notes[-1]["duration_beats"]) * spb + shift
    track = []
    k = 0
    while True:
        t = round(-1.0 + k * FRAME_S, 4)
        k += 1
        if t > end + 0.5:
            break
        frame = {"t": t, "hz": None, "clarity": 0.1, "rms": 0.0}
        if not silent and starts[0] <= t + 1e-9 and t < end - 1e-9:
            i = max(j for j, s in enumerate(starts) if s <= t + 1e-9)
            next_start = starts[i + 1] if i + 1 < len(starts) else None
            in_dip = (
                dips and next_start is not None and (i + 1) in REPEATED
                and t >= next_start - 0.05 - 1e-9
            )
            if in_dip:
                frame = {"t": t, "hz": None, "clarity": 0.2, "rms": 0.02}
            else:
                hz = fts.NOTE_FREQUENCIES_HZ[played.get(i, notes[i]["note"])] * 2 ** (cents / 1200)
                frame = {"t": t, "hz": hz, "clarity": 0.95, "rms": 0.2}
        track.append(frame)
    return track


def note_at(t, bpm=120):
    spb = 60.0 / bpm
    idx = [n["index"] for n in HIMNO["notes"] if n["start_beats"] * spb <= t + 1e-9]
    return idx[-1] if idx else None


def hand_vector(holes, hands=2):
    vec = [0.0] * fts.VISUAL_FEATURE_DIM
    vec[0] = 1.0 if hands >= 1 else 0.0
    vec[fts.VISUAL_HAND_SLOT_DIM] = 1.0 if hands >= 2 else 0.0
    for idx, covered in zip(HOLE_IDX, holes):
        vec[idx] = 1.0 if covered else 0.0
    return vec


def hand_frames(bpm=120, fingering=None, hands=2):
    """10 Hz hand frames whose holes follow the expected note (or `fingering[index]`)."""
    fingering = fingering or {}
    frames = []
    for k in range(int(16 * 120 / bpm / HAND_S)):
        t = round(k * HAND_S, 4)
        i = note_at(t, bpm)
        note = HIMNO["notes"][i]["note"]
        frames.append({"t": t, "features": hand_vector(fingering.get(i, fts.FRONT_HOLES[note]), hands)})
    return frames


def audio_frames(bpm=120, flute=0.95, not_flute_notes=()):
    frames = []
    for k in range(int(16 * 120 / bpm / HAND_S)):
        t = round(k * HAND_S, 4)
        value = 0.1 if note_at(t, bpm) in not_flute_notes else flute
        frames.append({"t": t, "features": [value] + [0.0] * (fts.AUDIO_FEATURE_DIM - 1)})
    return frames


def fake_head_probs(params, head, x):
    assert head == "sound"
    flute = np.clip(x[:, 0], 0.0, 1.0)
    probs = np.zeros((len(x), len(fts.SOUND_CLASSES)))
    probs[:, 0] = flute
    probs[:, fts.SOUND_CLASSES.index(fts.NO_FLUTE)] = 1.0 - flute
    return probs


def fake_finger_probs(params, x):
    return np.where(x[:, list(HOLE_IDX)] > 0.5, 0.95, 0.05)


def metrics(per_hole=None, **overrides):
    per_hole = per_hole or [
        {"hole": i + 1, "covered_count": 10, "open_count": 10} for i in range(fts.N_HOLES)
    ]
    value = {
        "visual_schema": fts.VISUAL_FEATURE_SCHEMA,
        "audio_schema": fts.AUDIO_FEATURE_SCHEMA,
        "tuning_offset_cents": 0.0,
        "fingers": {"test_accuracy": 0.95, "majority_baseline_accuracy": 0.6, "per_hole": per_hole},
    }
    value.update(overrides)
    return value


def score(track, bpm=120, audio=(), hands=(), params=None, model_metrics=None, **kwargs):
    return songs.score_song_performance(
        HIMNO, bpm, track, list(audio), list(hands), params, model_metrics, **kwargs
    )


def with_fake_model():
    return (
        patch.object(fts, "_head_probs", side_effect=fake_head_probs),
        patch.object(fts, "_finger_probs", side_effect=fake_finger_probs),
    )


# --------------------------------------------------------------------------- #
# S2 — catalog
# --------------------------------------------------------------------------- #
def test_catalog_matches_user_score_table():
    listed = songs.list_flute_songs()
    assert [s["id"] for s in listed] == ["himno_alegria"]
    song = listed[0]
    assert song["title"] == "Himno a la Alegría"
    assert (song["default_bpm"], song["min_bpm"], song["max_bpm"], song["beats_per_bar"]) == (120, 60, 120, 4)
    assert song["image"] == "/flute-songs/himno_la_alegria.png"
    notes = song["notes"]
    assert len(notes) == 30
    assert [n["index"] for n in notes] == list(range(30))
    assert [n["pass"] for n in notes] == [1] * 15 + [2] * 15

    # User table in seconds at 120 BPM (quarter = 0.5 s).
    pass_1 = [
        ("MI", 0.0, 0.5), ("MI", 0.5, 0.5), ("FA", 1.0, 0.5), ("SOL", 1.5, 0.5), ("SOL", 2.0, 0.5),
        ("FA", 2.5, 0.5), ("MI", 3.0, 0.5), ("RE", 3.5, 0.5), ("DO", 4.0, 0.5), ("DO", 4.5, 0.5),
        ("RE", 5.0, 0.5), ("MI", 5.5, 0.5), ("MI", 6.0, 0.5), ("RE", 6.5, 0.5), ("RE", 7.0, 1.0),
    ]
    pass_2 = [(n, s + 8.0, d) for n, s, d in pass_1[:12]] + [("RE", 14.0, 0.5), ("DO", 14.5, 0.5), ("DO", 15.0, 1.0)]
    seconds = [(n["note"], n["start_beats"] * 0.5, n["duration_beats"] * 0.5) for n in notes]
    assert seconds == pass_1 + pass_2
    assert [n["note"] for n in notes[12:15]] == ["MI", "RE", "RE"]
    assert [n["note"] for n in notes[27:30]] == ["RE", "DO", "DO"] and notes[29]["duration_beats"] == 2
    assert notes[15]["start_beats"] == 16


def test_catalog_listing_is_a_copy():
    listed = songs.list_flute_songs()
    listed[0]["notes"][0]["note"] = "LA"
    assert songs.FLUTE_SONGS["himno_alegria"]["notes"][0]["note"] == "MI"


# --------------------------------------------------------------------------- #
# S4/S5 — pitch-only scoring
# --------------------------------------------------------------------------- #
def test_perfect_performance_at_120_bpm_is_approved():
    res = score(performance())
    assert res["song_id"] == "himno_alegria" and res["tempo_bpm"] == 120
    assert res["notes_correct"] == 30 and res["notes_total"] == 30
    assert res["sound_score"] == 100 and res["total_score"] == 100
    assert res["posture_score"] is None and res["model_version"] is None
    assert res["latency_offset_ms"] == 0 and res["tuning_offset_cents"] == 0
    assert res["approved"] is True
    assert res["message"] == "Aprobado: 30 de 30 notas correctas (100%)."
    for n in res["notes"]:
        assert n["correct"] is True and n["detected_note"] == n["note"]
        assert n["pitch_share"] == 1.0
        assert n["timing_ok"] is True and abs(n["onset_ms"]) <= 1
        assert n["repeated"] is (n["index"] in REPEATED)
        assert n["articulation_ok"] is (True if n["index"] in REPEATED else None)
        assert n["flute_ok"] is None and n["posture_ok"] is None
        assert n["posture_reason"] and n["mismatched_holes"] == []
    assert res["notes"][15]["expected_start_s"] == 8.0 and res["notes"][29]["duration_s"] == 1.0


def test_constant_microphone_latency_is_compensated():
    res = score(performance(shift=0.2))
    assert res["latency_offset_ms"] == pytest.approx(200, abs=1)
    assert res["notes_correct"] == 30 and res["approved"] is True
    assert all(abs(n["onset_ms"]) <= 1 for n in res["notes"])


def test_latency_is_clamped():
    res = score(performance(shift=0.7))
    assert res["latency_offset_ms"] == 500


def test_wrong_note_is_reported_with_detected_note():
    res = score(performance(played={3: "LA"}))
    wrong = res["notes"][3]
    assert wrong["note"] == "SOL" and wrong["detected_note"] == "LA"
    assert wrong["pitch_share"] == 0 and wrong["correct"] is False
    assert all(n["correct"] for n in res["notes"] if n["index"] != 3)
    assert res["notes_correct"] == 29
    assert res["sound_score"] == pytest.approx(96.67, abs=0.01)
    assert res["total_score"] == res["sound_score"]  # no model: score = sound only
    assert res["approved"] is True
    assert res["message"] == "Aprobado: 29 de 30 notas correctas (97%)."


@pytest.mark.parametrize("delay,timing_ok,onset_ms,correct", [
    (0.125, True, 125.0, True),
    (0.2, False, 200.0, False),
    (0.3, False, None, False),
])
def test_late_onset_is_judged_against_150_ms(delay, timing_ok, onset_ms, correct):
    res = score(performance(late={2: delay}))
    note = res["notes"][2]
    assert note["timing_ok"] is timing_ok
    assert note["onset_ms"] == (pytest.approx(onset_ms, abs=1) if onset_ms is not None else None)
    assert note["correct"] is correct
    assert res["latency_offset_ms"] == 0
    assert all(n["correct"] and n["timing_ok"] for n in res["notes"] if n["index"] != 2)


def test_repeated_notes_need_an_rms_dip_for_timing():
    with_dip = score(performance(dips=True))
    without = score(performance(dips=False))
    for idx in REPEATED:
        assert with_dip["notes"][idx]["articulation_ok"] is True
        assert with_dip["notes"][idx]["timing_ok"] is True
        n = without["notes"][idx]
        assert n["repeated"] is True and n["articulation_ok"] is False
        assert n["onset_ms"] is None and n["timing_ok"] is None
        assert n["correct"] is True  # pitch ok and timing not false
    assert without["notes_correct"] == 30


def test_silence_scores_zero_and_fails():
    res = score(performance(silent=True))
    assert res["notes_correct"] == 0 and res["sound_score"] == 0 and res["total_score"] == 0
    assert res["approved"] is False and res["latency_offset_ms"] == 0
    assert res["message"] == "Reprobado: 0 de 30 notas correctas (0%)."
    assert all(n["detected_note"] is None and n["correct"] is False for n in res["notes"])
    assert all(n["timing_ok"] is (None if n["repeated"] else False) for n in res["notes"])


def test_tempo_scales_all_windows():
    slow = score(performance(bpm=60), bpm=60)
    assert slow["notes_correct"] == 30 and slow["approved"] is True
    assert slow["notes"][15]["expected_start_s"] == 16.0 and slow["notes"][29]["duration_s"] == 2.0
    mismatched = score(performance(bpm=120), bpm=60)
    assert mismatched["approved"] is False


def test_out_of_tune_flute_needs_the_model_tuning_offset():
    sharp = performance(cents=80)
    assert score(sharp)["notes_correct"] == 0
    with patch.object(fts, "_head_probs", side_effect=fake_head_probs), \
            patch.object(fts, "_finger_probs", side_effect=fake_finger_probs):
        res = score(sharp, params={}, model_metrics=metrics(tuning_offset_cents=50.0))
    assert res["tuning_offset_cents"] == 50.0 and res["notes_correct"] == 30


# --------------------------------------------------------------------------- #
# S6 — with an active model: flute check and finger head
# --------------------------------------------------------------------------- #
def test_model_scores_fingering_and_mixes_total():
    sol_as_la = fts.FRONT_HOLES["LA"]  # hole 3 open
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(
            performance(), audio=audio_frames(), hands=hand_frames(fingering={3: sol_as_la}),
            params={}, model_metrics=metrics(), model_version="flute-pitch-3.1.0",
        )
    assert res["model_version"] == "flute-pitch-3.1.0"
    bad = res["notes"][3]
    assert bad["posture_ok"] is False and bad["mismatched_holes"] == [3] and bad["posture_reason"] is None
    assert bad["correct"] is True  # fingering does not change the sound verdict
    for n in res["notes"]:
        assert n["flute_ok"] is True
        if n["index"] != 3:
            assert n["posture_ok"] is True and n["mismatched_holes"] == []
    assert res["sound_score"] == 100
    assert res["posture_score"] == pytest.approx(100 * 29 / 30, abs=0.01)
    assert res["total_score"] == pytest.approx(0.75 * 100 + 0.25 * 100 * 29 / 30, abs=0.01)
    assert res["approved"] is True


def test_non_flute_sound_makes_the_note_incorrect():
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(performance(), audio=audio_frames(not_flute_notes={5}), hands=hand_frames(),
                    params={}, model_metrics=metrics())
    assert res["notes"][5]["flute_ok"] is False and res["notes"][5]["correct"] is False
    assert res["notes_correct"] == 29


def test_hole_state_unseen_in_training_is_not_evaluable():
    per_hole = [{"hole": i + 1, "covered_count": 10, "open_count": 10} for i in range(fts.N_HOLES)]
    per_hole[6]["covered_count"] = 0  # only DO covers hole 7
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(performance(), audio=audio_frames(), hands=hand_frames(),
                    params={}, model_metrics=metrics(per_hole=per_hole))
    for n in res["notes"]:
        if n["index"] in DO_NOTES:
            assert n["posture_ok"] is None and "7" in n["posture_reason"] and n["correct"] is True
        else:
            assert n["posture_ok"] is True
    assert res["posture_score"] == 100 and res["total_score"] == 100


def test_missing_required_hands_is_not_evaluable():
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(performance(), audio=audio_frames(), hands=hand_frames(hands=1),
                    params={}, model_metrics=metrics())
    for n in res["notes"]:
        if n["note"] in fts.TWO_HAND_NOTES:
            assert n["posture_ok"] is None and "manos" in n["posture_reason"]
        else:
            assert n["posture_ok"] is True
    assert res["posture_score"] == 100


def test_unreliable_finger_head_falls_back_to_sound_only():
    weak = metrics()
    weak["fingers"].update(test_accuracy=0.5, majority_baseline_accuracy=0.6)
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(performance(played={3: "LA"}), audio=audio_frames(), hands=hand_frames(),
                    params={}, model_metrics=weak)
    assert all(n["posture_ok"] is None and n["posture_reason"] for n in res["notes"])
    assert all(n["flute_ok"] is True for n in res["notes"])
    assert res["posture_score"] is None and res["total_score"] == res["sound_score"]


def test_zero_sound_score_forces_zero_total_even_with_good_fingering():
    p1, p2 = with_fake_model()
    with p1, p2:
        res = score(performance(silent=True), audio=audio_frames(), hands=hand_frames(),
                    params={}, model_metrics=metrics())
    assert res["posture_score"] == 100
    assert res["sound_score"] == 0 and res["total_score"] == 0 and res["approved"] is False


# --------------------------------------------------------------------------- #
# Service entry point (model loading + validation)
# --------------------------------------------------------------------------- #
def request(**overrides):
    body = {
        "song_id": "himno_alegria",
        "tempo_bpm": 120,
        "pitch_track": performance(),
        "audio_schema": fts.AUDIO_FEATURE_SCHEMA,
        "audio_frames": [],
        "visual_schema": fts.VISUAL_FEATURE_SCHEMA,
        "hand_frames": [],
    }
    body.update(overrides)
    return body


def model_row(**metric_overrides):
    return SimpleNamespace(id=uuid4(), version="flute-pitch-3.1.0", activa=True, metricas=metrics(**metric_overrides))


@pytest.mark.asyncio
async def test_service_without_active_model_scores_pitch_only():
    db = SimpleNamespace(scalar=AsyncMock(return_value=None))
    res = await songs.score_flute_song(db, **request())
    assert res["model_version"] is None and res["notes_correct"] == 30


@pytest.mark.asyncio
async def test_service_ignores_legacy_model_without_loading_weights():
    legacy = model_row()
    legacy.metricas.pop("audio_schema")
    db = SimpleNamespace(scalar=AsyncMock(return_value=legacy))
    with patch.object(fts, "_params_for") as params:
        res = await songs.score_flute_song(db, **request(audio_frames=audio_frames()))
    params.assert_not_called()
    assert res["model_version"] is None and res["posture_score"] is None
    assert all(n["flute_ok"] is None for n in res["notes"])


@pytest.mark.asyncio
async def test_service_uses_current_active_model():
    db = SimpleNamespace(scalar=AsyncMock(return_value=model_row()))
    p1, p2 = with_fake_model()
    with p1, p2, patch.object(fts, "_params_for", return_value={}) as params:
        res = await songs.score_flute_song(
            db, **request(audio_frames=audio_frames(), hand_frames=hand_frames()),
        )
    params.assert_called_once()
    assert res["model_version"] == "flute-pitch-3.1.0"
    assert res["posture_score"] == 100 and res["total_score"] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,status,fragment", [
    ({"song_id": "no_existe"}, 404, "Canción no encontrada."),
    ({"tempo_bpm": 50}, 400, "60 y 120"),
    ({"tempo_bpm": 130}, 400, "60 y 120"),
    ({"audio_frames": [{"t": 0.0, "features": [0.0] * 48}]}, 400, "62 valores"),
    ({"hand_frames": [{"t": 0.0, "features": [0.0] * 49}]}, 400, "50 valores"),
    ({"audio_schema": "mel_mfcc_timbre"}, 400, "formato"),
])
async def test_service_rejects_invalid_input(overrides, status, fragment):
    db = SimpleNamespace(scalar=AsyncMock(return_value=None))
    with pytest.raises(SkillMatchException) as exc:
        await songs.score_flute_song(db, **request(**overrides))
    assert exc.value.statuscode == status
    assert fragment.lower() in exc.value.message.lower()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
BASE = "/api/ai/datasets/samples"


@pytest.fixture
async def admin_client():
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))

    async def override_db():
        yield session

    async def override_admin():
        return SimpleNamespace(id=uuid4(), role="ADMIN")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin_user] = override_admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


def test_song_routes_are_registered_before_sample_id_routes():
    # FastAPI wraps included routers lazily in app.routes; matching order is the router's order.
    prefix = dataset_router.prefix
    paths = [getattr(r, "path", "") for r in dataset_router.routes]
    songs_idx = paths.index(f"{prefix}/flute/songs")
    score_idx = paths.index(f"{prefix}/flute/score-song")
    first_dynamic = min(i for i, p in enumerate(paths) if p.startswith(f"{prefix}/{{sample_id}}"))
    assert songs_idx < first_dynamic and score_idx < first_dynamic


@pytest.mark.asyncio
async def test_get_songs_endpoint_returns_catalog(admin_client):
    response = await admin_client.get(f"{BASE}/flute/songs")
    assert response.status_code == 200
    body = response.json()
    assert body["statuscode"] == 200 and body["count"] == 1
    assert body["data"][0]["id"] == "himno_alegria" and len(body["data"][0]["notes"]) == 30


@pytest.mark.asyncio
async def test_score_song_endpoint_returns_verdict(admin_client):
    response = await admin_client.post(f"{BASE}/flute/score-song", json=request())
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["notes_correct"] == 30 and body["data"]["approved"] is True
    assert body["message"] == body["data"]["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,status", [
    ({"song_id": "no_existe"}, 404),
    ({"tempo_bpm": 50}, 422),
    ({"audio_schema": "mel_mfcc_timbre"}, 422),
    ({"visual_schema": "hand-landmarks-palm-v4"}, 422),
    ({"pitch_track": [{"t": -1.5, "hz": None, "clarity": 0.0, "rms": 0.0}]}, 422),
    ({"pitch_track": [{"t": 0.0, "hz": 500.0, "clarity": 1.5, "rms": 0.0}]}, 422),
    ({"pitch_track": [{"t": 0.0, "hz": None, "clarity": 0.0, "rms": 0.0}] * 4001}, 422),
    ({"audio_frames": [{"t": 0.0, "features": [0.0] * 48}]}, 400),
])
async def test_score_song_endpoint_validates_request(admin_client, overrides, status):
    response = await admin_client.post(f"{BASE}/flute/score-song", json=request(**overrides))
    assert response.status_code == status
    body = response.json()
    assert body["statuscode"] == status and body["data"] is None
    if status == 404:
        assert body["message"] == "Canción no encontrada."


@pytest.mark.asyncio
async def test_song_endpoints_are_hidden_from_non_admins():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{BASE}/flute/songs")
    assert response.status_code == 404
    assert response.json()["message"] == "Recurso no encontrado"
