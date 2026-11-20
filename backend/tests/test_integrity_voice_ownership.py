"""T8 / S3, S11: voice ownership (voiceprint) and lip-sync verdicts through the supervision policy."""
import json

import numpy as np
import pytest

from app.services.integrity import thresholds as t
from app.services.integrity import voiceprint as vp
from app.services.integrity.models import (
    AudioObservation, FrameObservation, FrameOcclusion, GazeEvidence, LipSyncResult, WindowObservation,
)
from app.services.integrity.policy import SupervisionProfile
from audio_fixtures import LevelExtractor, Segment, Trial, mouth_samples, pad, silence, speaking, syllables, voice

OWNERSHIP = {"VOICE_MISMATCH", "VOICE_UNVERIFIED", "MODEL_UNAVAILABLE", "LIP_SYNC_MISMATCH", "VOICE_DETECTED",
             "CLIENT_MISMATCH"}
ONE_VOICE = [Segment(0.0, 2.4, 0)]


def kinds(result):
    return [kind for kind in result["anomalies"] if kind in OWNERSHIP]


def enrolled(speaker=1, ambient=0.004):
    return vp.enroll(LevelExtractor(), voice(4.0, speaker), ambient_rms=ambient)


def window(trial, speaker=1, **kw):
    return trial.window(pad(voice(2.4, speaker)), **kw)


# ---- who is speaking --------------------------------------------------------------------------

def test_speech_without_an_enrolled_voiceprint_is_unverified_once_it_persists(monkeypatch):
    trial = Trial(monkeypatch, ONE_VOICE)
    first = window(trial)
    assert "VOICE_UNVERIFIED" not in kinds(first) and first["voice_match"] is None
    assert "VOICE_UNVERIFIED" in kinds(window(trial))


def test_no_speech_is_never_unverified(monkeypatch):
    trial = Trial(monkeypatch)
    for _ in range(3):
        assert kinds(trial.window(pad(silence(2.4)))) == []


def test_the_enrolled_voice_passes(monkeypatch):
    trial, record = Trial(monkeypatch, ONE_VOICE), enrolled(1)
    for _ in range(3):
        result = window(trial, 1, voiceprint=record)
        assert result["voice_match"] is True
        assert not {"VOICE_MISMATCH", "VOICE_UNVERIFIED"} & set(kinds(result))


def test_another_voice_is_a_mismatch_confirmed_by_the_second_evaluation(monkeypatch):
    trial, record = Trial(monkeypatch, ONE_VOICE), enrolled(1)
    first = window(trial, 2, voiceprint=record)
    assert first["voice_match"] is False and "VOICE_MISMATCH" not in kinds(first)
    second = window(trial, 2, voiceprint=record)
    assert second["voice_match"] is False and "VOICE_MISMATCH" in kinds(second)


def test_a_matching_evaluation_resets_the_mismatch_count(monkeypatch):
    trial, record = Trial(monkeypatch, ONE_VOICE), enrolled(1)
    window(trial, 2, voiceprint=record)
    window(trial, 1, voiceprint=record)
    assert "VOICE_MISMATCH" not in kinds(window(trial, 2, voiceprint=record))


def test_too_little_voiced_speech_is_no_verdict_and_leaves_the_count(monkeypatch):
    trial, record = Trial(monkeypatch), enrolled(1)
    window(trial, 2, voiceprint=record)
    short = trial.window(pad(voice(0.9, 2)), voiceprint=record)  # the buffer still holds the earlier voice
    brief = Trial(monkeypatch).window(pad(voice(0.5, 2)), voiceprint=record)
    assert brief["voice_match"] is None and "VOICE_MISMATCH" not in kinds(brief)
    assert short["voice_match"] is False  # buffered speech counts toward the one second


def test_a_short_silence_keeps_the_mismatch_count_and_a_long_one_forgets_it(monkeypatch):
    record = enrolled(1)
    trial = Trial(monkeypatch)
    window(trial, 2, voiceprint=record)
    trial.window(pad(silence(2.4)), voiceprint=record)
    assert "VOICE_MISMATCH" in kinds(window(trial, 2, voiceprint=record))
    trial = Trial(monkeypatch)
    window(trial, 2, voiceprint=record)
    trial.window(pad(silence(2.4)), voiceprint=record)
    trial.window(pad(silence(2.4)), voiceprint=record)
    assert "VOICE_MISMATCH" not in kinds(window(trial, 2, voiceprint=record))


def test_a_missing_speaker_model_is_model_unavailable_never_a_pass(monkeypatch):
    trial, record = Trial(monkeypatch), enrolled(1)
    trial.extractor.fail = vp.SpeakerModelUnavailable("missing")
    result = window(trial, 1, voiceprint=record)
    assert "MODEL_UNAVAILABLE" in kinds(result) and result["voice_match"] is None


def test_the_default_extractor_without_the_weights_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(vp, "EMBEDDING_MODEL", tmp_path / "absent.onnx")
    trial = Trial(monkeypatch, extractor=vp.SherpaEmbeddingExtractor())
    result = window(trial, 1, voiceprint=enrolled(1))
    assert "MODEL_UNAVAILABLE" in kinds(result) and result["voice_match"] is None


def test_an_unreadable_stored_voiceprint_fails_closed(monkeypatch):
    result = window(Trial(monkeypatch), 1, voiceprint={"embedding": "garbage"})
    assert "MODEL_UNAVAILABLE" in kinds(result)


def test_the_embedding_is_never_part_of_a_window_result(monkeypatch):
    record = enrolled(1)
    result = window(Trial(monkeypatch), 2, voiceprint=record)
    dumped = json.dumps(result, default=str)
    assert "embedding" not in dumped and str(record["embedding"][0])[:8] not in dumped


# ---- does the voice follow the mouth ----------------------------------------------------------

def talk(trial, env, mouth, **kw):
    return trial.window(pad(speaking(env)), gaze_samples=mouth, **kw)


def test_a_mouth_that_follows_the_voice_is_synced(monkeypatch):
    env = syllables(3)
    result = talk(Trial(monkeypatch, ONE_VOICE), env, mouth_samples(env))
    assert result["lip_sync"] == "synced" and result["mouth_sync"] is True
    assert not {"LIP_SYNC_MISMATCH", "VOICE_DETECTED"} & set(kinds(result))


@pytest.mark.parametrize("fake", ["still", "inverted", "unrelated"])
def test_a_voice_that_does_not_follow_the_mouth_is_confirmed_over_two_evaluations(monkeypatch, fake):
    env = syllables(3)
    trial = Trial(monkeypatch, ONE_VOICE)
    mouth = {"still": mouth_samples(env, still=True), "inverted": mouth_samples(env, invert=True),
             "unrelated": mouth_samples(syllables(17))}[fake]
    first = talk(trial, env, mouth)
    assert first["lip_sync"] == "unsynced" and first["mouth_sync"] is False
    assert "LIP_SYNC_MISMATCH" not in kinds(first)
    second = talk(trial, env, mouth)
    assert "LIP_SYNC_MISMATCH" in kinds(second) and "VOICE_DETECTED" not in kinds(second)


def test_a_synced_evaluation_resets_the_lip_sync_count(monkeypatch):
    env = syllables(3)
    trial = Trial(monkeypatch, ONE_VOICE)
    talk(trial, env, mouth_samples(env, still=True))
    talk(trial, env, mouth_samples(env))
    assert "LIP_SYNC_MISMATCH" not in kinds(talk(trial, env, mouth_samples(env, still=True)))


def test_a_lag_within_tolerance_is_synced(monkeypatch):
    env = syllables(3)
    assert talk(Trial(monkeypatch, ONE_VOICE), env, mouth_samples(env, offset_ms=150))["lip_sync"] == "synced"


def test_without_telemetry_and_with_few_frames_lip_sync_is_insufficient_and_voice_detected_stays(monkeypatch):
    env = syllables(3)
    result = talk(Trial(monkeypatch, ONE_VOICE), env, ())
    assert result["lip_sync"] == "insufficient" and result["mouth_sync"] is False
    assert kinds(result) == ["VOICE_DETECTED"]


def test_telemetry_contradicting_the_server_frames_is_ignored_and_flagged(monkeypatch):
    env = syllables(3)
    seen = FrameObservation(face_count=1, orientation="CENTER", pitch_deg=0.0, yaw_deg=0.0, gaze_h=0.0, gaze_v=0.0,
                            mouth_open_score=0.02, blendshapes={"jawOpen": 0.02})
    result = talk(Trial(monkeypatch, ONE_VOICE, mediapipe=seen), env, mouth_samples(env, mouth=0.9))
    assert "CLIENT_MISMATCH" in kinds(result)
    assert result["lip_sync"] == "insufficient"  # the browser's mouth was not used as evidence


def test_speech_with_no_face_is_voice_detected_never_lip_sync(monkeypatch):
    env = syllables(3)
    result = talk(Trial(monkeypatch, ONE_VOICE, faces=()), env, ())
    assert "VOICE_DETECTED" in kinds(result) and "LIP_SYNC_MISMATCH" not in kinds(result)


def test_speech_with_a_covered_mouth_is_voice_detected_not_lip_sync():
    covered = FrameObservation(face_count=1, occlusion=FrameOcclusion(mouth=True, measured=True))
    audio = AudioObservation(rms=0.07, speech_detected=True, diarized=False,
                             voice_status="unenrolled", voiced_chunks=80)
    unsynced = LipSyncResult("unsynced", 0.0, 0.0, 0, "telemetry")
    observation = WindowObservation(frames=(covered, covered, covered), audio=audio, lip_sync=unsynced,
                                    duration_ms=2400)
    result = SupervisionProfile().evaluate(observation).to_dict()
    assert "VOICE_DETECTED" in result["anomalies"] and "LIP_SYNC_MISMATCH" not in result["anomalies"]


def test_lip_sync_and_voice_fields_are_null_without_speech(monkeypatch):
    result = Trial(monkeypatch).window(pad(silence(2.4)))
    assert (result["lip_sync"], result["voice_match"]) == (None, None)
