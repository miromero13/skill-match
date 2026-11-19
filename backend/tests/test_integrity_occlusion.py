"""S7 / S8 / T7: covered face or mouth and a blocked or frozen camera, confirmed over time (>= 1 s)."""
import numpy as np
import pytest

from integrity_fixtures import (
    DARK_SKIN, HEIGHT, NEUTRAL, PALE_SKIN, SKIN, WIDTH, Harness, b64, face_b64, mp_faces, textured_b64,
)

from app.services.integrity import occlusion
from app.services.integrity.models import FrameObservation

STEP = 100  # ms between frames
CLEAN = 4  # clean frontal frames the trial's reference is built from


def run_window(clean, covered, cover, skin=SKIN, harness=None, script=None, mediapipe=None):
    """``clean`` frames then ``covered`` frames, one every 100 ms, in one window as long as the frames."""
    harness = harness or Harness()
    total = clean + covered
    images = [face_b64(i, skin=skin, cover=None if i < clean else cover) for i in range(total)]
    return harness.window(script or [[NEUTRAL]] * total, images=images, duration_ms=total * STEP, mediapipe=mediapipe)


# ---- S7: covered mouth ---------------------------------------------------------------------------

def test_a_live_face_with_noise_and_lighting_drift_is_never_occluded():
    res = run_window(16, 0, None)
    assert res["anomalies"] == []
    assert res["occlusion"] == {"face": False, "mouth": False}
    assert res["camera_blocked"] is False


@pytest.mark.parametrize("cover", ["mouth_hand", "mouth_mask"])
def test_a_mouth_covered_for_900_ms_is_not_an_incident(cover):
    res = run_window(CLEAN, 9, cover)
    assert res["anomalies"] == []
    assert res["occlusion"] == {"face": False, "mouth": False}


@pytest.mark.parametrize("cover", ["mouth_hand", "mouth_mask"])
def test_a_mouth_covered_for_1100_ms_is_mouth_occluded(cover):
    res = run_window(CLEAN, 11, cover)
    assert res["anomalies"] == ["MOUTH_OCCLUDED"]
    assert res["occlusion"] == {"face": False, "mouth": True}


@pytest.mark.parametrize("skin", [SKIN, DARK_SKIN, PALE_SKIN])
def test_the_reference_is_per_person_so_every_skin_tone_works(skin):
    assert run_window(16, 0, None, skin=skin)["anomalies"] == []
    assert run_window(CLEAN, 11, "mouth_hand", skin=skin)["anomalies"] == ["MOUTH_OCCLUDED"]


def test_a_covered_mouth_run_continues_across_windows():
    harness = Harness()
    first = run_window(CLEAN, 6, "mouth_hand", harness=harness)
    assert first["anomalies"] == []  # 600 ms so far
    images = [face_b64(40 + i, cover="mouth_hand") for i in range(6)]
    second = harness.window([[NEUTRAL]] * 6, images=images, duration_ms=600)
    assert second["anomalies"] == ["MOUTH_OCCLUDED"]


def test_uncovering_the_mouth_ends_the_run():
    harness = Harness()
    run_window(CLEAN, 6, "mouth_hand", harness=harness)
    harness.window([[NEUTRAL]] * 4, images=[face_b64(60 + i) for i in range(4)], duration_ms=400)
    images = [face_b64(80 + i, cover="mouth_hand") for i in range(6)]
    assert harness.window([[NEUTRAL]] * 6, images=images, duration_ms=600)["anomalies"] == []


# ---- S7: covered face ----------------------------------------------------------------------------

@pytest.mark.parametrize("cover", ["face_hand", "face_black"])
def test_a_covered_face_is_face_occluded_not_mouth_occluded(cover):
    res = run_window(CLEAN, 11, cover)
    assert res["anomalies"] == ["FACE_OCCLUDED"]
    assert res["occlusion"] == {"face": True, "mouth": False}


def test_a_covered_face_for_900_ms_is_not_an_incident():
    assert run_window(CLEAN, 9, "face_black")["anomalies"] == []


def test_mediapipe_hallucinating_a_covered_face_is_caught_by_the_detector_collapse():
    """MediaPipe still reports one face (hallucinated landmarks) while YuNet finds nothing and a cover is on the mouth."""
    harness = Harness(mediapipe=[mp_faces(1)])
    total = CLEAN + 11
    images = [face_b64(i, cover=None if i < CLEAN else "mouth_hand") for i in range(total)]
    script = [[NEUTRAL]] * CLEAN + [[]] * 11
    geometry = tuple(float(v) for v in NEUTRAL[4:14])
    stub = [FrameObservation(face_count=1, orientation="CENTER", pitch_deg=0.0, yaw_deg=0.0, face_geometry=geometry)]
    res = harness.window(script, images=images, duration_ms=total * STEP, mediapipe=stub)
    assert res["anomalies"] == ["FACE_OCCLUDED"]


def test_a_detector_collapse_alone_is_not_an_occlusion():
    harness = Harness(mediapipe=[mp_faces(1)])
    total = CLEAN + 11
    images = [face_b64(i) for i in range(total)]
    geometry = tuple(float(v) for v in NEUTRAL[4:14])
    stub = [FrameObservation(face_count=1, orientation="CENTER", pitch_deg=0.0, yaw_deg=0.0, face_geometry=geometry)]
    res = harness.window([[NEUTRAL]] * CLEAN + [[]] * 11, images=images, duration_ms=total * STEP, mediapipe=stub)
    assert res["anomalies"] == []


def test_a_turned_head_is_not_judged_for_occlusion():
    # YuNet rows with the nose far to the side: orientation is not CENTER, so the patches are not compared.
    from integrity_fixtures import row

    turned = row(shift=0)
    turned[8] = 175  # nose x
    harness = Harness()
    run_window(CLEAN, 0, None, harness=harness)
    images = [face_b64(50 + i, cover="face_black") for i in range(12)]
    res = harness.window([[turned]] * 12, images=images, duration_ms=1200)
    assert "FACE_OCCLUDED" not in res["anomalies"] and "MOUTH_OCCLUDED" not in res["anomalies"]


# ---- the per-frame decision rule -------------------------------------------------------------------

REF = {"n": 5.0, "skin_cr": 150.0, "skin_cb": 110.0, "sim": 0.8, "yunet": 0.95,
       "eyes_d": 10.0, "eyes_e": 100.0, "nose_d": 4.0, "nose_e": 60.0, "mouth_d": 9.0, "mouth_e": 70.0}


def measure(eyes=(10.0, 100.0), nose=(4.0, 60.0), mouth=(9.0, 70.0), skin=(150.0, 110.0)):
    return occlusion.OcclusionMeasure(
        skin=skin, distance={"eyes": eyes[0], "nose": nose[0], "mouth": mouth[0]},
        edge={"eyes": eyes[1], "nose": nose[1], "mouth": mouth[1]},
    )


@pytest.mark.parametrize(
    ("kwargs", "judge_kwargs", "face", "mouth"),
    [
        ({}, {}, False, False),
        ({"mouth": (9.0, 10.0)}, {}, False, True),  # texture lost, same chroma ratio: edge <= 20 %: a hand
        ({"mouth": (40.0, 70.0)}, {}, False, True),  # chroma moved 31: a mask, texture intact
        ({"mouth": (9.0, 30.0)}, {}, False, False),  # edge at 43 % with the same chroma: not covered
        ({"mouth": (22.0, 70.0)}, {}, False, False),  # chroma moved 13 but the texture is there
        ({"mouth": (22.0, 22.0)}, {}, False, True),  # edge at 31 % and chroma moved 13: covered
        ({"nose": (4.0, 5.0), "mouth": (9.0, 5.0)}, {}, False, True),  # mask: nose and mouth, eyes visible
        ({"eyes": (10.0, 5.0), "mouth": (9.0, 5.0)}, {}, True, False),
        ({"mouth": (9.0, 5.0)}, {"yunet_score": None, "mediapipe_saw_face": True, "yunet_ran": True}, True, False),
        ({"mouth": (9.0, 5.0)}, {"similarity": 0.5}, True, False),  # identity similarity fell 0.3
        ({"mouth": (9.0, 5.0), "skin": (120.0, 128.0)}, {}, True, False),
        ({"skin": (120.0, 128.0)}, {"yunet_score": None, "mediapipe_saw_face": True, "yunet_ran": True}, True, False),
        ({}, {"similarity": 0.5}, False, False),  # identity alone is only support
        ({}, {"yunet_score": None, "mediapipe_saw_face": True, "yunet_ran": True}, False, False),
    ],
)
def test_per_frame_decision_rule(kwargs, judge_kwargs, face, mouth):
    judge_kwargs = {"yunet_score": 0.95, **judge_kwargs}
    verdict = occlusion.judge(measure(**kwargs), REF, **judge_kwargs)
    assert (verdict.face, verdict.mouth) == (face, mouth)


def test_a_region_without_reference_texture_cannot_lose_it():
    flat = {**REF, "mouth_e": 1.0}
    assert occlusion.judge(measure(mouth=(9.0, 0.0)), flat, yunet_score=0.95).mouth is False


def test_the_reference_only_learns_from_clean_frames():
    harness = Harness()
    run_window(CLEAN, 8, "mouth_hand", harness=harness)
    ref = harness.state.get_track("trial", "occlusion_ref")
    assert ref["n"] == CLEAN  # the covered frames did not teach it
    assert ref["mouth_e"] > 20


# ---- S8: camera health -----------------------------------------------------------------------------

def solid(value):
    return b64(np.full((HEIGHT, WIDTH, 3), value, dtype=np.uint8))


def noisy_black(seed):
    rng = np.random.default_rng(seed)
    return b64(np.clip(rng.normal(3, 1.5, (HEIGHT, WIDTH, 3)), 0, 255).astype(np.uint8))


@pytest.mark.parametrize("kind", ["black", "noisy_black", "uniform"])
def test_black_or_uniform_frames_are_a_blocked_camera_not_an_absent_face(kind):
    frames = {
        "black": [solid(0)] * 3,
        "noisy_black": [noisy_black(i) for i in range(3)],
        "uniform": [solid(128)] * 3,
    }[kind]
    res = Harness().window([[]] * 3, images=frames, times=[0, 800, 1600])
    assert res["anomalies"] == ["CAMERA_BLOCKED"]
    assert res["camera_blocked"] is True
    assert res["face_count"] == 0


def test_a_single_black_frame_is_not_a_blocked_camera():
    frames = [textured_b64(1), solid(0), textured_b64(2), textured_b64(3)]
    res = Harness().window([[NEUTRAL]] * 4, images=frames, times=[0, 600, 1200, 1800])
    assert res["anomalies"] == []


def test_identical_frames_for_1500_ms_are_a_frozen_camera():
    res = Harness().window([[NEUTRAL]] * 4, images=[face_b64(1)] * 4, times=[0, 600, 1200, 1800])
    assert res["anomalies"] == ["CAMERA_BLOCKED"]
    assert res["camera_blocked"] is True
    assert res["face_count"] == 1  # the frozen image still shows a face: the camera is the problem


def test_identical_frames_for_less_than_1500_ms_are_not_frozen():
    res = Harness().window([[NEUTRAL]] * 2, images=[face_b64(1)] * 2, times=[0, 1200])
    assert res["anomalies"] == []


def test_a_live_camera_with_a_still_person_is_not_frozen():
    res = Harness().window([[NEUTRAL]] * 4, images=[face_b64(i) for i in range(4)], times=[0, 600, 1200, 1800])
    assert res["anomalies"] == []


def test_a_frozen_camera_run_continues_across_windows():
    harness = Harness()
    first = harness.window([[NEUTRAL]] * 2, images=[face_b64(1)] * 2, times=[0, 1200])
    assert first["anomalies"] == []
    second = harness.window([[NEUTRAL]] * 2, images=[face_b64(1)] * 2, times=[0, 1200])
    assert second["anomalies"] == ["CAMERA_BLOCKED"]


def test_a_changing_image_after_a_frozen_stretch_ends_the_run():
    harness = Harness()
    harness.window([[NEUTRAL]] * 2, images=[face_b64(1)] * 2, times=[0, 1200])
    assert harness.window([[NEUTRAL]] * 2, images=[face_b64(2), face_b64(3)], times=[0, 1200])["anomalies"] == []


# ---- real models ---------------------------------------------------------------------------------------

def test_the_real_models_do_not_crash_on_a_synthetic_frame():
    from app.services import vision_models

    if not (vision_models.YUNET_MODEL_PATH.is_file() and vision_models.SFACE_MODEL_PATH.is_file()):
        pytest.skip("face models are not provisioned")
    from app.services.integrity.engine import IntegrityEngine
    from app.services.integrity.state import InMemoryStateStore

    engine = IntegrityEngine.create(state=InMemoryStateStore(), landmarker_provider=lambda: None)
    frames = [face_b64(i) for i in range(3)]
    window = engine.observe_window(frames, [0.0] * 38_400, 2400, session_key="real", frame_times_ms=[0, 800, 1600])
    assert len(window.frames) == 3
    assert all(not frame.model_unavailable for frame in window.frames)


# ---- API contract ------------------------------------------------------------------------------------

def test_new_kinds_are_audiovisual_incidents_and_the_window_response_exposes_the_new_fields():
    import uuid
    from datetime import datetime, timezone

    from app.schemas.browser_supervision import AVWindowResponse, IncidentRequest
    from app.services.browser_supervision_service import AV_KINDS, BROWSER_KINDS

    for kind in ("FACE_OCCLUDED", "MOUTH_OCCLUDED", "CAMERA_BLOCKED"):
        IncidentRequest(event_id=uuid.uuid4(), kind=kind, observed_at=datetime.now(timezone.utc))
        assert kind in AV_KINDS and kind not in BROWSER_KINDS and len(kind) <= 32
    response = AVWindowResponse(
        window_id=uuid.uuid4(), face_count=1, head_orientation="CENTER", identity_match=None, speech_detected=False,
        noise_level=0.0, anomalies=[], incidents_created=[], occlusion={"face": True, "mouth": False},
        camera_blocked=True,
    )
    dumped = response.model_dump()
    assert dumped["occlusion"] == {"face": True, "mouth": False} and dumped["camera_blocked"] is True
