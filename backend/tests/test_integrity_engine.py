"""S9 / T5: characterization of the shared integrity engine and its facade.

Every window case runs through BOTH the legacy ``ContinuousSupervisionService`` facade and the new
``IntegrityEngine`` with the same injected stubs, so the extraction is proven behavior-preserving.
"""
import base64
import itertools
import sys
import types
import uuid
from collections import OrderedDict

import cv2
import numpy as np
import pytest

from app.services.biometric_service import SFACE_COSINE_THRESHOLD
from app.services.calibration_speaker_service import CalibrationSpeakerService
from app.services.continuous_supervision_service import ContinuousSupervisionService as Facade
from app.services.integrity import frame_analyzer

SAMPLES_2400 = 38_400  # 2.4 s at 16 kHz
NEUTRAL = [80, 40, 120, 150, 115, 95, 165, 95, 140, 126, 120, 155, 160, 155, 0.95]
DOWN = [80, 45, 120, 145, 115, 108, 165, 108, 140, 137, 120, 153, 160, 153, 0.92]
SIDE = [80, 40, 120, 150, 115, 95, 165, 95, 149, 126, 124, 155, 164, 155, 0.93]
REFERENCE = np.zeros(128, dtype=np.float32)
REFERENCE[0] = 1.0
WINDOW_KEYS = {
    "face_count", "head_orientation", "identity_match", "speech_detected", "mouth_moving",
    "mouth_sync", "multiple_speakers", "noise_level", "anomalies", "occlusion", "camera_blocked",
    "voice_match", "lip_sync",
}


_frame_counter = itertools.count()


def frame_b64() -> str:
    """A different noisy image on every call: a live camera, never a covered, flat or frozen one (T7 / S8)."""
    rng = np.random.default_rng(next(_frame_counter))
    ok, buf = cv2.imencode(".jpg", rng.integers(40, 200, (240, 320, 3), dtype=np.uint8))
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


def frames(count: int) -> list[str]:
    return [frame_b64() for _ in range(count)]


class SequenceDetector:
    """YuNet stand-in: call N returns the face rows of ``script[N % len(script)]`` (empty = no face)."""

    def __init__(self, script):
        self.script = script
        self.calls = 0

    def setInputSize(self, _size):
        pass

    def detect(self, _img):
        rows = self.script[self.calls % len(self.script)]
        self.calls += 1
        return 1, (np.asarray(rows, dtype=np.float32) if rows else None)


class StubRecognizer:
    def __init__(self, feature):
        self._feature = np.asarray(feature, dtype=np.float32)

    def alignCrop(self, image, _face):
        return image

    def feature(self, _aligned):
        return self._feature


def one_hot(index: int) -> np.ndarray:
    vec = np.zeros(128, dtype=np.float32)
    vec[index] = 1.0
    return vec


def quiet(n=SAMPLES_2400):
    return [0.0] * n


def speech(n=SAMPLES_2400):
    return (0.1 * np.sin(2 * np.pi * 200 * np.arange(n) / 16_000)).astype(float).tolist()


def loud(n=SAMPLES_2400):
    return [0.25 * ((-1) ** (i % 2)) for i in range(n)]


def fake_vad(monkeypatch, is_speech: bool) -> None:
    module = types.ModuleType("webrtcvad")
    module.Vad = lambda _mode: types.SimpleNamespace(is_speech=lambda _raw, _rate: is_speech)
    monkeypatch.setitem(sys.modules, "webrtcvad", module)


class Segment:
    def __init__(self, start, end, speaker):
        self.start, self.end, self.speaker = start, end, speaker


def with_segments(monkeypatch, segments) -> None:
    monkeypatch.setattr(CalibrationSpeakerService, "segments", staticmethod(lambda _audio: segments))


@pytest.fixture(params=["facade", "engine"])
def run(request, monkeypatch):
    """Runs one window through the legacy facade or through a fresh engine with the same stubs."""

    states: dict = {}

    def execute(frames, audio, *, detector=None, recognizer=None, reference=None, duration_ms=2400, key=None):
        key = key or f"t-{uuid.uuid4()}"
        if request.param == "facade":
            monkeypatch.setattr(Facade, "get_vision_models", staticmethod(lambda: (detector, recognizer)))
            monkeypatch.setattr(frame_analyzer, "get_landmarker", lambda: None)
            embedding = None if reference is None else "[" + ",".join(str(float(v)) for v in reference) + "]"
            return Facade.assess_window(
                frames, audio, trial_id=key, biometric_embedding_json=embedding, duration_ms=duration_ms,
            )
        from app.services.integrity.audio_analyzer import AudioAnalyzer
        from app.services.integrity.engine import IntegrityEngine
        from app.services.integrity.frame_analyzer import FrameAnalyzer
        from app.services.integrity.policy import SupervisionProfile
        from app.services.integrity.state import InMemoryStateStore

        state = states.setdefault(key, InMemoryStateStore())
        engine = IntegrityEngine(
            frame_analyzer=FrameAnalyzer(
                state, vision_provider=lambda: (detector, recognizer), landmarker_provider=lambda: None,
            ),
            audio_analyzer=AudioAnalyzer(state),
        )
        result = engine.assess_window(
            frames, audio, duration_ms=duration_ms, reference_embedding=reference,
            session_key=key, profile=SupervisionProfile(gaze_runs=state),
        )
        return result.to_dict()

    return execute


# ---- evidence and model availability ----------------------------------------------------------

def test_model_unavailable_is_not_a_clean_face(run):
    res = run(frames(1), quiet(), detector=None)
    assert set(res) == WINDOW_KEYS
    assert res["anomalies"] == ["MODEL_UNAVAILABLE"]
    assert (res["face_count"], res["head_orientation"], res["identity_match"]) == (0, "UNKNOWN", None)
    assert res["mouth_sync"] is None


def test_video_missing_is_not_a_clean_face(run):
    res = run([], quiet(), detector=SequenceDetector([[]]))
    assert res["anomalies"] == ["VIDEO_MISSING"]
    assert (res["face_count"], res["head_orientation"], res["identity_match"]) == (0, "UNKNOWN", None)


def test_undecodable_frames_are_video_missing(run):
    res = run(["not-a-jpeg", ""], quiet(), detector=SequenceDetector([[NEUTRAL]]))
    assert "VIDEO_MISSING" in res["anomalies"]
    assert res["face_count"] == 0


def test_audio_missing_when_absent_or_inconsistent_with_duration(run):
    assert run(frames(1), None, detector=SequenceDetector([[NEUTRAL]]))["anomalies"] == ["AUDIO_MISSING"]
    short = run(frames(1), quiet(SAMPLES_2400 // 2), detector=SequenceDetector([[NEUTRAL]]))
    assert short["anomalies"] == ["AUDIO_MISSING"]
    assert short["speech_detected"] is False


def test_clean_window_reports_no_anomalies(run):
    res = run(frames(1), quiet(), detector=SequenceDetector([[NEUTRAL]]))
    assert res == {
        "face_count": 1, "head_orientation": "CENTER", "identity_match": None, "speech_detected": False,
        "mouth_moving": False, "mouth_sync": None, "multiple_speakers": False, "noise_level": 0.0,
        "anomalies": [], "occlusion": {"face": False, "mouth": False}, "camera_blocked": False,
        "voice_match": None, "lip_sync": None,
    }


# ---- face count and head pose -----------------------------------------------------------------

def test_face_absent(run):
    res = run(frames(2), quiet(), detector=SequenceDetector([[]]))
    assert res["anomalies"] == ["FACE_ABSENT"]
    assert res["face_count"] == 0


def test_multiple_faces_in_a_single_frame_are_not_confirmed(run):
    res = run(frames(3), quiet(), detector=SequenceDetector([[NEUTRAL], [NEUTRAL, SIDE], [NEUTRAL]]))
    assert res["anomalies"] == []
    assert res["face_count"] == 1


def test_multiple_faces(run):
    res = run(frames(2), quiet(), detector=SequenceDetector([[NEUTRAL, SIDE]]))
    assert res["anomalies"] == ["MULTIPLE_FACES"]
    assert res["face_count"] == 2
    assert res["head_orientation"] == "UNKNOWN"


def test_head_pose_down_is_sustained_against_the_session_baseline(run):
    res = run(frames(3), quiet(), detector=SequenceDetector([[NEUTRAL], [DOWN], [DOWN]]))
    assert res["anomalies"] == ["HEAD_POSE_DOWN"]
    assert res["head_orientation"] == "DOWN"
    assert res["face_count"] == 1


def test_head_pose_side(run):
    res = run(frames(2), quiet(), detector=SequenceDetector([[SIDE]]))
    assert res["anomalies"] == ["HEAD_POSE_SIDE"]
    assert res["head_orientation"] == "RIGHT"


def test_a_single_off_axis_frame_in_a_long_window_is_tolerated(run):
    res = run(frames(4), quiet(), detector=SequenceDetector([[NEUTRAL], [SIDE], [NEUTRAL], [NEUTRAL]]))
    assert res["anomalies"] == []
    assert res["head_orientation"] == "CENTER"


# ---- identity ---------------------------------------------------------------------------------

def test_identity_mismatch_is_confirmed_by_a_second_window(run):
    window = dict(detector=SequenceDetector([[NEUTRAL]]), recognizer=StubRecognizer(one_hot(1)),
                  reference=REFERENCE, key="mismatch")
    first = run(frames(2), quiet(), **window)
    assert (first["anomalies"], first["identity_match"]) == ([], None)
    second = run(frames(2), quiet(), **window)
    assert second["anomalies"] == ["IDENTITY_MISMATCH"]
    assert second["identity_match"] is False


def test_identity_match(run):
    res = run(frames(2), quiet(), detector=SequenceDetector([[NEUTRAL]]),
              recognizer=StubRecognizer(one_hot(0)), reference=REFERENCE)
    assert res["anomalies"] == []
    assert res["identity_match"] is True


def test_identity_is_not_judged_without_a_reference(run):
    res = run(frames(1), quiet(), detector=SequenceDetector([[NEUTRAL]]), recognizer=StubRecognizer(one_hot(1)))
    assert res["identity_match"] is None


# ---- audio ------------------------------------------------------------------------------------

def test_voice_without_mouth_movement_is_voice_detected(run, monkeypatch):
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 2.0, 0)])
    res = run(frames(2), speech(), detector=SequenceDetector([[NEUTRAL]]))
    assert res["anomalies"] == ["VOICE_DETECTED"]
    assert (res["speech_detected"], res["mouth_sync"], res["multiple_speakers"]) == (True, False, False)


def test_voice_with_the_camera_unavailable_cannot_be_lip_sync_checked(run, monkeypatch):
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 2.0, 0)])
    res = run(frames(1), speech(), detector=None)
    assert res["anomalies"] == ["MODEL_UNAVAILABLE"]
    assert (res["speech_detected"], res["mouth_sync"]) == (True, None)


def test_multiple_speakers(run, monkeypatch):
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 1.0, 0), Segment(1.0, 2.0, 1)])
    # T8 / S2: several speakers are confirmed by two diarizations in a row (the first one is only pending).
    first = run(frames(2), speech(), detector=SequenceDetector([[NEUTRAL]]), key="two-voices")
    assert "MULTIPLE_SPEAKERS" not in first["anomalies"] and first["multiple_speakers"] is False
    res = run(frames(2), speech(), detector=SequenceDetector([[NEUTRAL]]), key="two-voices")
    # speech with no enrolled voiceprint is also unverified once it persists (T8 / S3)
    assert res["anomalies"] == ["MULTIPLE_SPEAKERS", "VOICE_UNVERIFIED"]
    assert (res["multiple_speakers"], res["mouth_sync"]) == (True, False)


def test_overlapping_voices_count_as_multiple_speakers(run, monkeypatch):
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 1.0, 0), Segment(0.6, 1.5, 1)])  # 0.4 s of overlap: no waiting (T8)
    res = run(frames(2), speech(), detector=SequenceDetector([[NEUTRAL]]))
    assert res["anomalies"] == ["MULTIPLE_SPEAKERS"]


def test_high_noise_without_speech(run, monkeypatch):
    fake_vad(monkeypatch, False)
    res = run(frames(1), loud(), detector=SequenceDetector([[NEUTRAL]]))
    assert res["anomalies"] == ["HIGH_NOISE"]
    assert res["noise_level"] == 0.25
    assert res["speech_detected"] is False


def test_moderate_noise_is_high_only_when_it_is_not_speech(run, monkeypatch):
    moderate = [0.16 * ((-1) ** (i % 2)) for i in range(SAMPLES_2400)]
    fake_vad(monkeypatch, False)
    assert run(frames(1), moderate, detector=SequenceDetector([[NEUTRAL]]))["anomalies"] == ["HIGH_NOISE"]
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 2.0, 0)])
    res = run(frames(2), moderate, detector=SequenceDetector([[NEUTRAL]]))
    assert "HIGH_NOISE" not in res["anomalies"]


# ---- engine-only surface ----------------------------------------------------------------------

def test_package_layout_exposes_the_documented_components():
    from app.services.integrity import audio_analyzer, engine, frame_analyzer, models, policy, state, sync_analyzer

    assert engine.IntegrityEngine and frame_analyzer.FrameAnalyzer and audio_analyzer.AudioAnalyzer
    assert sync_analyzer.SyncAnalyzer and state.InMemoryStateStore and state.SessionStateStore
    assert policy.SupervisionProfile and policy.CalibrationProfile
    assert models.FrameObservation and models.AudioObservation and models.WindowObservation


def test_calibration_profile_is_an_unfilled_skeleton():
    from app.services.integrity.models import WindowObservation
    from app.services.integrity.policy import CalibrationProfile

    with pytest.raises(NotImplementedError):
        CalibrationProfile().evaluate(WindowObservation())


def test_frame_observation_keeps_the_legacy_dict_shape():
    from app.services.integrity.models import FrameObservation

    assert FrameObservation(face_count=1, orientation="CENTER").to_legacy_dict() == {
        "face_count": 1, "orientation": "CENTER", "identity_match": None, "mouth_open_score": 0.0,
        "mouth_patch": None,
    }
    flagged = FrameObservation(face_count=0, model_unavailable=True).to_legacy_dict()
    assert flagged["model_unavailable"] is True and flagged["orientation"] == "UNKNOWN"


class FakeCategory:
    def __init__(self, name, score):
        self.category_name, self.score = name, score


class FakeLandmarker:
    """MediaPipe FaceLandmarker stand-in: one frontal face with a known eye-look pattern."""

    def detect(self, _image):
        points = [types.SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(478)]
        for index, (x, y, z) in {
            10: (0.5, 0.2, 0.0), 152: (0.5, 0.8, 0.0), 33: (0.4, 0.4, 0.0), 263: (0.6, 0.4, 0.0),
            1: (0.5, 0.5, 0.0), 78: (0.43, 0.65, 0.0), 308: (0.57, 0.65, 0.0),
            13: (0.5, 0.64, 0.0), 14: (0.5, 0.66, 0.0),
        }.items():
            points[index] = types.SimpleNamespace(x=x, y=y, z=z)
        return types.SimpleNamespace(
            face_landmarks=[points],
            face_blendshapes=[[FakeCategory("eyeLookDownLeft", 0.1), FakeCategory("eyeLookInRight", 0.3),
                               FakeCategory("jawOpen", 0.0)]],
            facial_transformation_matrixes=[np.eye(4)],
        )


def test_frame_analyzer_exposes_pose_and_blendshape_measurements():
    from app.services.integrity.frame_analyzer import FrameAnalyzer
    from app.services.integrity.state import InMemoryStateStore

    analyzer = FrameAnalyzer(InMemoryStateStore(), vision_provider=lambda: (None, None),
                             landmarker_provider=lambda: None)
    image = np.full((120, 160, 3), 128, dtype=np.uint8)
    obs = analyzer.analyze_frame(image, None, None, None, session_key="mp", landmarker=FakeLandmarker())
    assert (obs.face_count, obs.orientation) == (1, "CENTER")
    assert obs.pitch_deg == pytest.approx(0.0, abs=1.0) and obs.yaw_deg == pytest.approx(0.0, abs=1.0)
    assert obs.blendshapes["eyeLookDownLeft"] == pytest.approx(0.1)
    assert obs.blendshapes["eyeLookInRight"] == pytest.approx(0.3)
    assert obs.landmarks is None
    kept = FrameAnalyzer(InMemoryStateStore(), vision_provider=lambda: (None, None),
                         landmarker_provider=lambda: None, keep_landmarks=True)
    assert kept.analyze_frame(image, None, None, None, landmarker=FakeLandmarker()).landmarks.shape == (478, 3)


def test_identity_similarity_is_recorded_alongside_the_verdict():
    from app.services.integrity.frame_analyzer import FrameAnalyzer
    from app.services.integrity.state import InMemoryStateStore

    analyzer = FrameAnalyzer(InMemoryStateStore(), vision_provider=lambda: (None, None),
                             landmarker_provider=lambda: None)
    image = np.full((240, 320, 3), 128, dtype=np.uint8)
    same = analyzer.analyze_frame(image, SequenceDetector([[NEUTRAL]]), StubRecognizer(one_hot(0)), REFERENCE)
    assert same.identity_similarity == pytest.approx(1.0) and same.identity_match is True
    other = analyzer.analyze_frame(image, SequenceDetector([[NEUTRAL]]), StubRecognizer(one_hot(1)), REFERENCE)
    assert other.identity_similarity == pytest.approx(0.0) and other.identity_match is False
    assert SFACE_COSINE_THRESHOLD > 0.0


def test_state_store_is_bounded_and_evicts_the_least_recently_used_session():
    from app.services.integrity.state import MAX_TRACKED_SESSIONS, InMemoryStateStore

    store = InMemoryStateStore()
    metrics = {"pitch_deg": 0.0, "yaw_deg": 0.0, "eye_look_down": 0.0, "pitch_ratio": 0.5,
               "nose_mouth_eye_ratio": 0.4}
    assert store.update_baseline(None, metrics, True) is None
    assert store.update_baseline("never-frontal", metrics, False) is None
    for index in range(MAX_TRACKED_SESSIONS + 1):
        assert store.update_baseline(f"s{index}", metrics, True)["samples"] == 1.0
    assert len(store.baselines) == MAX_TRACKED_SESSIONS
    assert "s0" not in store.baselines and f"s{MAX_TRACKED_SESSIONS}" in store.baselines
    assert store.update_baseline("s1", metrics, True)["samples"] == 2.0


def test_state_store_buffers_voiced_audio_and_clears_it_on_silence():
    from app.services.integrity.state import InMemoryStateStore

    store = InMemoryStateStore()
    first = np.ones(38_400, dtype=np.float32)
    second = np.zeros(10, dtype=np.float32)
    assert store.combine_with_previous("k", first, remember=True).size == 38_400
    assert store.combine_with_previous("k", second, remember=False).size == 38_410  # buffer capped at 2.4 s
    store.clear_voiced_audio("k")
    assert store.combine_with_previous("k", second, remember=False).size == 10
    assert store.combine_with_previous(None, second, remember=True).size == 10


def test_state_store_can_wrap_externally_owned_containers_and_lock():
    import threading

    from app.services.integrity.state import InMemoryStateStore

    baselines, audio, lock = OrderedDict(), OrderedDict(), threading.RLock()
    store = InMemoryStateStore(baselines=baselines, audio_state=audio, lock=lock)
    store.update_baseline("k", {"pitch_deg": 0.0}, True)
    assert "k" in baselines and store.baselines is baselines


def test_sync_coexistence_rules():
    from app.services.integrity.sync_analyzer import voice_mouth_coexistence

    def verdict(**kw):
        base = dict(speech_detected=True, multiple_speakers=False, visual_unavailable=False,
                    face_count=1, mouth_moving=True)
        return voice_mouth_coexistence(**{**base, **kw})

    assert verdict().mouth_sync is True and verdict().anomaly is None
    assert (verdict(mouth_moving=False).mouth_sync, verdict(mouth_moving=False).anomaly) == (False, "VOICE_DETECTED")
    assert (verdict(face_count=0).mouth_sync, verdict(face_count=0).anomaly) == (False, "VOICE_DETECTED")
    assert (verdict(multiple_speakers=True).mouth_sync, verdict(multiple_speakers=True).anomaly) == (
        False, "MULTIPLE_SPEAKERS")
    assert (verdict(visual_unavailable=True).mouth_sync, verdict(visual_unavailable=True).anomaly) == (None, None)
    assert (verdict(speech_detected=False).mouth_sync, verdict(speech_detected=False).anomaly) == (None, None)


def test_engine_matches_facade_for_a_window_with_everything_wrong(monkeypatch):
    """Same inputs, same stubs: engine and facade agree on every field, anomalies included and ordered."""
    fake_vad(monkeypatch, True)
    with_segments(monkeypatch, [Segment(0.0, 1.0, 0), Segment(1.0, 2.0, 1)])
    images = frames(4)
    detector = SequenceDetector([[NEUTRAL], [NEUTRAL], [DOWN], [DOWN]])
    monkeypatch.setattr(Facade, "get_vision_models", staticmethod(lambda: (detector, StubRecognizer(one_hot(1)))))
    monkeypatch.setattr(frame_analyzer, "get_landmarker", lambda: None)
    legacy = Facade.assess_window(images, loud(), trial_id="everything", duration_ms=2400,
                                  biometric_embedding_json="[" + ",".join(map(str, REFERENCE.tolist())) + "]")
    # The first window of an identity mismatch is only pending (confirmed by a second one), so it is not listed;
    # the two speakers are pending too (T8: two diarizations in a row), so the mouth rule reports the voice.
    assert legacy["anomalies"] == ["HEAD_POSE_DOWN", "HIGH_NOISE", "VOICE_DETECTED"]
    assert legacy["identity_match"] is None

    from app.services.integrity.audio_analyzer import AudioAnalyzer
    from app.services.integrity.engine import IntegrityEngine
    from app.services.integrity.frame_analyzer import FrameAnalyzer
    from app.services.integrity.state import InMemoryStateStore

    state = InMemoryStateStore()
    detector.calls = 0
    engine = IntegrityEngine(
        FrameAnalyzer(state, vision_provider=lambda: (detector, StubRecognizer(one_hot(1))),
                      landmarker_provider=lambda: None),
        AudioAnalyzer(state),
    )
    from app.services.integrity.policy import SupervisionProfile

    modern = engine.assess_window(images, loud(), duration_ms=2400, reference_embedding=REFERENCE,
                                  session_key="everything", profile=SupervisionProfile(gaze_runs=state)).to_dict()
    assert modern == legacy
