"""T9 / S9: the pre-exam calibration judged by the integrity engine's CalibrationProfile (no HTTP).

The vision boundary is replaced by ``FakeFrames`` (each frame string maps to the observation the real analyzer would
measure); the audio side is the real ``AudioAnalyzer`` over a faked VAD, diarization and speaker embedding.
"""
import json
import sys
import types

import numpy as np
import pytest

from app.services.integrity import calibration as cal, messages as m, thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.models import FrameBatch, FrameObservation, FrameOcclusion
from app.services.integrity.state import InMemoryStateStore
from audio_fixtures import LevelExtractor, Segment, SR, install_fake_vad, mouth_samples, silence, speaking, syllables, voice
from integrity_fixtures import face_b64

BOX = (0.30, 0.20, 0.375, 0.62)
AMBIENT_MS = 2000
PHRASE_S, PAUSE_S = 4.0, 4.0  # the speech segment is 8 s: phrase first, silent from 4.5 s on
REFERENCE = np.eye(1, 128, dtype=np.float32)[0]


def face(yaw=0.0, pitch=0.0, **kw):
    base = dict(face_count=1, orientation="CENTER", pitch_deg=pitch, yaw_deg=yaw, gaze_h=0.0, gaze_v=0.0,
                identity_match=True, identity_similarity=0.9, face_box=BOX, face_score=0.9, pose_3d=True,
                occlusion=FrameOcclusion(measured=True), frame_delta=5.0, mouth_open_score=0.05)
    base.update(kw)
    return FrameObservation(**base)


class FakeFrames:
    """The FrameAnalyzer boundary: ``by_frame`` maps a frame string to its observation."""

    def __init__(self):
        self.state = InMemoryStateStore()
        self.by_frame: dict = {}
        self.unavailable = False
        self.calls: list = []

    def analyze_frames(self, frames, reference, session_key, times_ms=None):
        self.calls.append((list(frames), reference is not None, session_key))
        if self.unavailable:
            return FrameBatch(model_unavailable=True)
        if session_key and "occlusion_ref" not in (self.state.tracks.get(session_key) or {}):
            self.state.set_track(session_key, "occlusion_ref", {"n": 4.0, "skin_cr": 150.0, "skin_cb": 100.0})
        return FrameBatch(frames=tuple(self.by_frame[f] for f in frames))


TARGET_POSE = {"CENTER": (0, 0, 0.0, 0.0), "TOP_LEFT": (-9, -9, -0.5, -0.4), "TOP_RIGHT": (-9, 9, 0.5, -0.4),
               "BOTTOM_LEFT": (9, -9, -0.5, 0.4), "BOTTOM_RIGHT": (9, 9, 0.5, 0.4)}


class Calibration:
    """One complete, passing calibration; tests change one thing and assert the check that catches it."""

    def __init__(self, monkeypatch, action="TURN_LEFT"):
        install_fake_vad(monkeypatch)
        self.action = action
        self.fake = FakeFrames()
        self.segments = lambda audio: [Segment(0.0, len(audio) / SR, 0)]
        self.extractor = LevelExtractor()
        sign = -1 if action == "TURN_LEFT" else 1
        self.movement = [face_b64(i) for i in range(12)]
        for index, frame in enumerate(self.movement):
            self.fake.by_frame[frame] = face(yaw=sign * 25.0 if 4 <= index < 8 else 0.0)
        self.points = {}
        for target, (pitch, yaw, gaze_h, gaze_v) in TARGET_POSE.items():
            self.points[target] = [f"{target}-{i}" for i in range(3)]
            for frame in self.points[target]:
                self.fake.by_frame[frame] = face(yaw=yaw, pitch=pitch, gaze_h=gaze_h, gaze_v=gaze_v)
        env = syllables(3, chunks=int(PHRASE_S * 1000 / 30))
        self.audio = np.concatenate([silence(AMBIENT_MS / 1000), speaking(env), silence(PAUSE_S)])
        duration_ms = self.audio.size * 1000 // SR
        self.times = list(range(AMBIENT_MS, duration_ms + 1, 100))
        telemetry = mouth_samples(np.concatenate([env, np.zeros(int(PAUSE_S * 1000 / 30))]))  # still mouth in the pause
        self.mouth = [(s.t_ms + AMBIENT_MS, s.mouth_open) for s in telemetry]
        self.voice = [f"voice-{i}" for i in range(len(self.times))]
        for frame, at in zip(self.voice, self.times):
            level = float(np.interp(at - AMBIENT_MS, [s.t_ms for s in telemetry], [s.mouth_open for s in telemetry]))
            self.fake.by_frame[frame] = face(mouth_open_score=level)

    def evidence(self, **changes):
        base = dict(action=self.action, frames=self.movement, gaze_points=self.points, audio=self.audio,
                    ambient_ms=AMBIENT_MS, voice_frames=list(zip(self.times, self.voice)), mouth=self.mouth,
                    reference=REFERENCE, camera_label="Physical webcam")
        base.update(changes)
        return cal.CalibrationEvidence(**base)

    def engine(self):
        audio = AudioAnalyzer(self.fake.state, speaker_segments=lambda a: self.segments(a), extractor=self.extractor,
                              vad_floor=0.0, min_speaker_s=t.CAL_SPEAKER_MIN_DURATION_S)
        return cal.CalibrationEngine(self.fake, audio, self.extractor)

    def run(self, **changes):
        return self.engine().assess(self.evidence(**changes))

    def rejected(self, **changes):
        with pytest.raises(cal.CalibrationRejected) as caught:
            self.run(**changes)
        return caught.value


@pytest.fixture
def good(monkeypatch):
    return Calibration(monkeypatch)


def only(good, index, **kw):
    """Replaces the observation of one movement frame."""
    good.fake.by_frame[good.movement[index]] = face(**kw)


# ---- a complete calibration ------------------------------------------------------------------------------------


def test_a_complete_calibration_passes_every_required_check_and_yields_supervision_inputs(good):
    output = good.run()
    assert set(output.checks) == cal.REQUIRED_CHECKS and all(output.checks.values())
    assert output.gaze_zone.yaw_min < 0 < output.gaze_zone.yaw_max
    assert output.voiceprint["ambient_rms"] == pytest.approx(0.0, abs=1e-6) and output.voiceprint["voiced_s"] >= 3.0
    assert output.occlusion_ref["n"] >= t.OCC_REF_MIN_SAMPLES
    json.dumps([output.gaze_zone.to_dict(), output.voiceprint, output.occlusion_ref])  # persistable as JSON


@pytest.mark.parametrize("action", ["TURN_LEFT", "TURN_RIGHT"])
def test_the_requested_direction_is_judged_with_the_3d_yaw_sign(monkeypatch, action):
    assert all(Calibration(monkeypatch, action).run().checks.values())
    other = Calibration(monkeypatch, "TURN_RIGHT" if action == "TURN_LEFT" else "TURN_LEFT")
    wrong = other.engine().assess(other.evidence(action=action)) if False else None  # noqa: F841
    with pytest.raises(cal.CalibrationRejected) as caught:
        other.engine().assess(other.evidence(action=action))
    assert caught.value.check == "liveness" and caught.value.message == m.LIVENESS


# ---- movement: faces, camera, identity, pose -------------------------------------------------------------------


@pytest.mark.parametrize("count", [0, 2])
def test_exactly_one_face_in_every_frame(good, count):
    only(good, 6, face_count=count, orientation="UNKNOWN", pitch_deg=None, yaw_deg=None, occlusion=None)
    error = good.rejected()
    assert (error.check, error.message, error.status) == ("single_face", m.SINGLE_FACE, 400)


def test_a_covered_mouth_for_a_continuous_stretch_is_rejected(good):
    for index in (1, 2):
        only(good, index, occlusion=FrameOcclusion(mouth=True, measured=True))
    error = good.rejected()
    assert (error.check, error.message) == ("mouth_uncovered", m.MOUTH_COVERED)


def test_a_covered_face_for_a_continuous_stretch_is_rejected(good):
    for index in (8, 9, 10):
        only(good, index, occlusion=FrameOcclusion(face=True, measured=True))
    error = good.rejected()
    assert (error.check, error.message) == ("face_uncovered", m.FACE_COVERED)


def test_a_single_covered_frame_is_not_a_stretch(good):
    only(good, 2, occlusion=FrameOcclusion(mouth=True, measured=True))
    assert all(good.run().checks.values())


def test_no_frame_with_an_occlusion_verdict_is_not_a_pass_by_omission(good):
    for index in range(12):
        only(good, index, occlusion=None, yaw=-25.0 if 4 <= index < 8 else 0.0)
    error = good.rejected()
    assert (error.check, error.message) == ("occlusion_reference", m.OCCLUSION_UNJUDGED)


def test_a_blocked_camera_is_rejected(good):
    for index in range(12):
        only(good, index, camera_blocked=True, yaw=-25.0 if 4 <= index < 8 else 0.0)
    error = good.rejected()
    assert (error.check, error.message) == ("camera_live", m.CAMERA_BLOCKED)


def test_a_frozen_or_looped_feed_is_rejected_server_side_without_any_label(good):
    for index in range(1, 6):
        only(good, index, frame_delta=0.05, yaw=-25.0 if 4 <= index < 8 else 0.0)
    error = good.rejected(camera_label="")
    assert (error.check, error.message) == ("camera_live", m.CAMERA_FROZEN)


def test_a_repeated_image_is_not_a_live_sequence(good):
    frames = [good.movement[0], good.movement[1]] * 6  # two distinct images only
    error = good.rejected(frames=frames)
    assert (error.check, error.message) == ("camera_live", m.DIFFERENT_FRAMES)


@pytest.mark.parametrize("label", ["OBS Virtual Camera", "ManyCam", "v4l2loopback device", "Some virtual cam"])
def test_a_virtual_camera_label_is_rejected_but_only_advisorily(good, label):
    error = good.rejected(camera_label=label)
    assert (error.check, error.message) == ("camera_live", m.PHYSICAL_CAMERA)


def test_identity_must_match_the_enrolled_face_in_every_frame(good):
    only(good, 5, identity_match=False, yaw=-25.0)
    error = good.rejected()
    assert (error.check, error.message) == ("identity", m.IDENTITY)
    only(good, 5, identity_match=None, yaw=-25.0)
    assert good.rejected().message == m.IDENTITY_UNKNOWN


def test_no_head_turn_is_rejected(good):
    for index in range(4, 8):
        only(good, index, yaw=-4.0)
    error = good.rejected()
    assert (error.check, error.message) == ("liveness", m.LIVENESS)


def test_a_single_frame_at_the_turn_angle_is_not_a_turn(good):
    for index in (5, 6, 7):
        only(good, index, yaw=0.0)
    assert good.rejected().check == "liveness"


@pytest.mark.parametrize("change", [{"yaw": 20.0}, {"pitch": 30.0}, {"gaze_h": 0.9}])
def test_the_first_frame_must_be_frontal_in_pose_and_gaze(good, change):
    only(good, 0, **change)
    error = good.rejected()
    assert (error.check, error.message) == ("frontal", m.FRONTAL)


def test_the_head_must_return_to_where_it_started(good):
    for index in (9, 10, 11):
        only(good, index, yaw=-12.0)
    assert good.rejected().check == "frontal"


def test_liveness_needs_the_3d_pose_never_the_2d_fallback(good):
    for index in range(12):
        only(good, index, pose_3d=False, yaw=-25.0 if 4 <= index < 8 else 0.0)
    error = good.rejected()
    assert (error.check, error.message, error.status) == ("liveness", m.POSE_3D_UNAVAILABLE, 503)


@pytest.mark.parametrize("change,check,message", [
    ({"face_box": (0.0, 0.0, 0.05, 0.05)}, "framing", m.FRAMING),
    ({"face_box": None}, "framing", m.FRAMING),
    ({"face_score": 0.5}, "framing", m.FRAMING),
])
def test_the_face_must_be_framed(good, change, check, message):
    only(good, 3, **change)
    error = good.rejected()
    assert (error.check, error.message) == (check, message)


def test_lighting_and_focus_are_still_enforced(good, monkeypatch):
    from app.services.integrity import environment
    monkeypatch.setattr(environment, "lighting_ok", lambda env: False)
    assert (good.rejected().check, good.rejected().message) == ("lighting", m.LIGHTING)
    monkeypatch.undo()
    install_fake_vad(monkeypatch)
    monkeypatch.setattr(environment, "sharp_ok", lambda env: False)
    assert good.rejected().message == m.SHARPNESS
    monkeypatch.undo()
    install_fake_vad(monkeypatch)
    monkeypatch.setattr(environment, "screen_pattern", lambda gray: True)
    assert good.rejected().message == m.SCREEN_PATTERN


@pytest.mark.parametrize("raw,message", [("not-an-image" * 10, m.INVALID_IMAGE)])
def test_an_undecodable_image_is_rejected(good, raw, message):
    error = good.rejected(frames=[raw] + good.movement[1:])
    assert (error.check, error.message) == ("frames", message)


# ---- the gaze zone ---------------------------------------------------------------------------------------------


def test_corners_that_cannot_be_told_apart_are_rejected(good):
    for target, frames in good.points.items():
        for frame in frames:
            good.fake.by_frame[frame] = face()
    error = good.rejected()
    assert (error.check, error.message) == ("gaze_zone", m.GAZE_CALIBRATION_ERRORS["NOT_DISTINGUISHABLE"][1])


def test_a_second_person_while_looking_at_a_corner_is_rejected(good):
    good.fake.by_frame["TOP_LEFT-1"] = face(face_count=2)
    error = good.rejected()
    assert (error.check, error.message) == ("gaze_zone", m.GAZE_CALIBRATION_ERRORS["MULTIPLE_FACES"][1])


def test_the_face_at_the_centre_point_must_be_the_enrolled_one(good):
    for frame in good.points["CENTER"]:
        good.fake.by_frame[frame] = face(identity_match=False)
    assert good.rejected().message == m.IDENTITY


def test_a_missing_target_is_rejected(good):
    error = good.rejected(gaze_points={k: v for k, v in good.points.items() if k != "BOTTOM_RIGHT"})
    assert error.check == "gaze_zone" and error.status == 400


# ---- the silence and speech steps -----------------------------------------------------------------------------


def replace_audio(good, ambient=None, speech=None, pause=None):
    env = syllables(3, chunks=int(PHRASE_S * 1000 / 30))
    return np.concatenate([silence(AMBIENT_MS / 1000) if ambient is None else ambient,
                           speaking(env) if speech is None else speech,
                           silence(PAUSE_S) if pause is None else pause])


def test_speech_during_the_silent_step_is_rejected(good):
    ambient = np.concatenate([silence(0.5), voice(1.0), silence(0.5)])
    error = good.rejected(audio=replace_audio(good, ambient=ambient))
    assert (error.check, error.message) == ("background_quiet", m.SPEECH_DURING_SILENCE)


def test_too_much_background_noise_in_the_silent_step_is_rejected(good):
    noise = (0.02 * np.sin(2 * np.pi * 440.0 * np.arange(AMBIENT_MS * SR // 1000) / SR)).astype(np.float32)
    error = good.rejected(audio=replace_audio(good, ambient=noise))
    assert (error.check, error.message) == ("background_quiet", m.BACKGROUND_NOISE)


def test_too_little_speech_is_rejected(good):
    mostly_silent = np.concatenate([silence(1.0), voice(0.2), silence(PHRASE_S + PAUSE_S - 1.2)])
    error = good.rejected(audio=np.concatenate([silence(AMBIENT_MS / 1000), mostly_silent]))
    assert (error.check, error.message) == ("microphone", m.NOT_ENOUGH_SPEECH)


def test_speech_during_the_final_pause_is_rejected(good):
    error = good.rejected(audio=replace_audio(good, pause=np.concatenate([silence(0.4), voice(1.0), silence(2.6)])))
    assert (error.check, error.message) == ("speech_pause", m.SPEECH_DURING_PAUSE)


def test_two_speakers_are_rejected(good):
    good.segments = lambda audio: [Segment(0.3, 1.5, 0), Segment(2.0, 3.5, 1)]
    error = good.rejected()
    assert (error.check, error.message) == ("single_speaker", m.MORE_THAN_ONE_VOICE)


def test_overlapping_voices_are_rejected(good):
    good.segments = lambda audio: [Segment(0.3, 2.0, 0), Segment(1.5, 3.5, 1)]
    error = good.rejected()
    assert (error.check, error.message) == ("no_overlap", m.OVERLAPPING_VOICES)


def test_a_voice_that_diarization_cannot_confirm_is_rejected(good):
    good.segments = lambda audio: []
    assert good.rejected().message == m.SINGLE_VOICE_UNCONFIRMED


@pytest.mark.parametrize("ambient_ms,seconds", [(1000, 7.0), (2000, 6.0), (2000, 10.5)])
def test_the_recording_lengths_are_bounded(good, ambient_ms, seconds):
    audio = np.concatenate([silence(ambient_ms / 1000), voice(seconds)])
    error = good.rejected(audio=audio, ambient_ms=ambient_ms)
    assert (error.check, error.message) == ("audio", m.AUDIO_SIZE)


# ---- voice: video, telemetry, lip-sync -------------------------------------------------------------------------


def test_the_spoken_frames_must_cover_the_recording(good):
    frames = list(zip(good.times, good.voice))
    for bad in (frames[::5], list(reversed(frames)), frames[:12]):
        assert good.rejected(voice_frames=bad).message == m.VOICE_VIDEO


def test_a_second_face_while_speaking_is_rejected(good):
    good.fake.by_frame["voice-30"] = face(face_count=2)
    error = good.rejected()
    assert (error.check, error.message) == ("single_face", m.VOICE_SINGLE_FACE)


def test_the_face_while_speaking_must_be_the_enrolled_one(good):
    middle = len(good.voice) // 2
    good.fake.by_frame[good.voice[middle]] = face(identity_match=False, mouth_open_score=0.2)
    error = good.rejected()
    assert (error.check, error.message) == ("identity", m.VOICE_IDENTITY)


def test_a_covered_mouth_while_speaking_is_rejected(good):
    for frame in good.voice[20:40]:
        good.fake.by_frame[frame] = face(occlusion=FrameOcclusion(mouth=True, measured=True), mouth_open_score=0.2)
    error = good.rejected()
    assert (error.check, error.message) == ("mouth_uncovered", m.MOUTH_COVERED)


def test_a_voice_with_a_still_mouth_is_rejected(good):
    error = good.rejected(mouth=[(at, 0.05) for at, _ in good.mouth])
    assert (error.check, error.message) == ("mouth_audio_sync", m.VOICE_WITHOUT_MOUTH)


def test_missing_mouth_telemetry_is_not_a_pass_by_omission(good):
    error = good.rejected(mouth=[])
    assert error.check == "mouth_audio_sync" and error.message == m.VOICE_CALIBRATION_ERRORS["NO_MOUTH"][1]


def test_untrusted_mouth_telemetry_rejects_the_calibration(good):
    error = good.rejected(mouth=[(at, value + 0.6) for at, value in good.mouth])
    assert (error.check, error.message) == ("mouth_telemetry", m.VOICE_CALIBRATION_ERRORS["UNTRUSTED_TELEMETRY"][1])


def test_the_server_measuring_no_mouth_on_its_frames_leaves_the_telemetry_unverifiable(good):
    for frame in good.voice:
        good.fake.by_frame[frame] = face(mouth_open_score=0.0)
    assert good.rejected().check == "mouth_telemetry"


# ---- fail closed: missing models -------------------------------------------------------------------------------


def test_missing_vision_models_fail_closed_with_503(good):
    good.fake.unavailable = True
    error = good.rejected()
    assert (error.status, error.message) == (503, m.VISION_UNAVAILABLE)


def test_a_missing_speaker_embedding_model_fails_closed_with_503(good):
    good.extractor.fail = vp.SpeakerModelUnavailable("missing")
    error = good.rejected()
    assert error.status == 503 and error.message == m.SPEAKER_MODELS_UNAVAILABLE


def test_missing_diarization_models_fail_closed_with_503(good):
    def broken(_audio):
        raise RuntimeError("no diarization models")

    good.segments = broken
    error = good.rejected()
    assert error.status == 503 and error.message == m.SPEAKER_MODELS_UNAVAILABLE


def test_a_missing_voice_activity_detector_fails_closed_with_503(good, monkeypatch):
    monkeypatch.setitem(sys.modules, "webrtcvad", None)  # import webrtcvad -> ImportError
    error = good.rejected()
    assert (error.check, error.status, error.message) == ("background_quiet", 503, m.VAD_UNAVAILABLE)


def test_incomplete_evidence_never_yields_ready(good, monkeypatch):
    monkeypatch.setattr(cal, "REQUIRED_CHECKS", cal.REQUIRED_CHECKS | {"a_future_check"})
    assert good.rejected().check == "incomplete"


def test_the_checks_a_calibration_requires_are_the_old_ones_plus_the_engine_ones():
    old = {"lighting", "framing", "single_face", "microphone", "background_quiet", "identity", "liveness",
           "passive_screen_check", "single_speaker", "no_overlap", "mouth_audio_sync", "speech_pause"}
    assert old <= cal.REQUIRED_CHECKS
    assert {"camera_live", "face_uncovered", "mouth_uncovered", "frontal", "gaze_zone", "voiceprint",
            "occlusion_reference", "mouth_telemetry", "sharpness"} <= cal.REQUIRED_CHECKS


# ---- the unified analyzers ------------------------------------------------------------------------------------


def test_the_vad_floor_knob_feeds_quiet_speech_to_the_vad_as_the_pre_exam_silence_check_always_did(monkeypatch):
    module = types.ModuleType("webrtcvad")
    module.Vad = lambda _mode: types.SimpleNamespace(is_speech=lambda _raw, _rate: True)  # anything it hears is speech
    monkeypatch.setitem(sys.modules, "webrtcvad", module)
    quiet_voice = (0.002 * np.sin(2 * np.pi * 200.0 * np.arange(SR) / SR)).astype(np.float32)  # rms 0.0014 < 0.005
    assert AudioAnalyzer(InMemoryStateStore()).analyze(quiet_voice).voiced_flags == []  # supervision: below the floor
    strict = AudioAnalyzer(InMemoryStateStore(), vad_floor=0.0).analyze(quiet_voice)
    assert sum(strict.voiced_flags) > 30 and not strict.vad_unavailable


# ---- the pre-exam contract that predates the zone and the browser telemetry (kept working until the next slice) ----


def test_without_zone_points_and_telemetry_the_rest_is_still_enforced_and_the_server_mouth_is_the_series(good):
    output = good.run(gaze_points=None, mouth=None)
    assert set(output.checks) == cal.REQUIRED_CHECKS - cal.NEW_CONTRACT_CHECKS and all(output.checks.values())
    assert output.gaze_zone is None and output.voiceprint is None  # nothing to seed supervision with: not a full pass


def test_the_server_mouth_series_still_judges_a_voice_with_a_still_mouth(good):
    for frame in good.voice:
        good.fake.by_frame[frame] = face(mouth_open_score=0.05)
    error = good.rejected(gaze_points=None, mouth=None)
    assert (error.check, error.message) == ("mouth_audio_sync", m.VOICE_WITHOUT_MOUTH)


def test_without_zone_points_the_movement_rules_still_reject(good):
    only(good, 5, face_count=2, orientation="UNKNOWN", pitch_deg=None, yaw_deg=None, occlusion=None)
    assert good.rejected(gaze_points=None, mouth=None).check == "single_face"
