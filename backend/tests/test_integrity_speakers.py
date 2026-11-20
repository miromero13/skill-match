"""T8 / S2, S4: the per-trial rolling voiced buffer, confirmed multi-speaker detection and BACKGROUND_AUDIO."""
import numpy as np
import pytest

from app.core.exceptions import SkillMatchException
from app.services.integrity import thresholds as t
from app.services.integrity import voiceprint as vp
from audio_fixtures import LevelExtractor, Segment, Trial, pad, silence, tone, voice, SR

TWO_SPEAKERS = [Segment(0.0, 1.2, 0), Segment(1.2, 2.4, 1)]


AUDIO_KINDS = {"MULTIPLE_SPEAKERS", "BACKGROUND_AUDIO", "HIGH_NOISE", "MODEL_UNAVAILABLE"}


def kinds(result):
    """The audio-side incidents under test (the still mouth of a synthetic voice is the lip-sync tests' business)."""
    return [kind for kind in result["anomalies"] if kind in AUDIO_KINDS]


# ---- rolling voiced buffer ----------------------------------------------------------------------

def test_diarization_runs_over_the_rolling_voiced_buffer_not_just_the_last_window(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 2.0, 0)])
    for _ in range(3):
        trial.window(pad(voice(2.4)))
    assert trial.diarized_lengths == [38_400, 76_800, 96_000]  # grows by a window, then capped at ~6 s


def test_only_voiced_audio_is_buffered(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 1.0, 0)])
    trial.window(pad(silence(0.6), voice(1.8)))
    assert trial.diarized_lengths == [int(1.8 * SR)]


def test_a_short_silence_keeps_the_buffer_and_a_long_one_clears_it(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 1.0, 0)])
    trial.window(pad(voice(2.4)))
    trial.window(pad(silence(2.4)))  # 2.4 s of silence: less than the clearing time
    trial.window(pad(voice(2.4)))
    assert trial.diarized_lengths == [38_400, 76_800]
    trial.window(pad(silence(2.4)))
    trial.window(pad(silence(2.4)))  # 4.8 s of silence: stale speech is forgotten
    trial.window(pad(voice(2.4)))
    assert trial.diarized_lengths[-1] == 38_400


def test_buffer_is_kept_per_trial_state_and_never_without_a_session(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 1.0, 0)])
    trial.window(pad(voice(2.4)))
    other = Trial(monkeypatch, [Segment(0.0, 1.0, 0)])
    other.window(pad(voice(2.4)))
    assert other.diarized_lengths == [38_400]


# ---- multiple speakers are confirmed ---------------------------------------------------------------

def test_two_speakers_in_one_evaluation_are_pending_and_two_in_a_row_are_confirmed(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    first = trial.window(pad(voice(2.4)))
    assert kinds(first) == [] and first["multiple_speakers"] is False
    second = trial.window(pad(voice(2.4)))
    assert kinds(second) == ["MULTIPLE_SPEAKERS"] and second["multiple_speakers"] is True


def test_an_evaluation_with_one_speaker_resets_the_confirmation(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    trial.window(pad(voice(2.4)))
    trial.segments = [Segment(0.0, 2.4, 0)]
    trial.window(pad(voice(2.4)))
    trial.segments = TWO_SPEAKERS
    assert kinds(trial.window(pad(voice(2.4)))) == []


def test_a_window_without_speech_resets_the_confirmation(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    trial.window(pad(voice(2.4)))
    trial.window(pad(silence(2.4)))
    assert kinds(trial.window(pad(voice(2.4)))) == []


def test_overlap_of_at_least_the_minimum_is_confirmed_at_once(monkeypatch):
    overlap = t.MULTI_SPEAKER_IMMEDIATE_OVERLAP_S
    trial = Trial(monkeypatch, [Segment(0.0, 1.5, 0), Segment(1.5 - overlap, 2.4, 1)])
    assert kinds(trial.window(pad(voice(2.4)))) == ["MULTIPLE_SPEAKERS"]


def test_a_short_overlap_still_needs_two_evaluations(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 1.0, 0), Segment(0.85, 1.6, 1)])  # 0.15 s of overlap
    assert kinds(trial.window(pad(voice(2.4)))) == []
    assert kinds(trial.window(pad(voice(2.4)))) == ["MULTIPLE_SPEAKERS"]


def test_without_per_trial_state_a_single_window_is_never_confirmed_by_count_alone(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    trial.profile.store = None
    trial.profile.runs.store = None
    assert kinds(trial.window(pad(voice(2.4)), stateful=False)) == []


# ---- the diarized cluster that is not the enrolled voice -------------------------------------------

def enrolled(speaker=1):
    return vp.enroll(LevelExtractor(), voice(4.0, speaker), ambient_rms=0.004)


def test_a_foreign_cluster_next_to_the_enrolled_voice_is_multiple_speakers_immediately(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    window = pad(voice(1.2, 1), voice(1.2, 2))
    result = trial.window(window, voiceprint=enrolled(1))
    assert kinds(result) == ["MULTIPLE_SPEAKERS"] and result["multiple_speakers"] is True


def test_two_clusters_without_a_voiceprint_are_not_immediate(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    assert kinds(trial.window(pad(voice(1.2, 1), voice(1.2, 2)))) == []


def test_two_clusters_that_both_differ_from_the_voiceprint_are_not_immediate(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    assert "MULTIPLE_SPEAKERS" not in kinds(trial.window(pad(voice(1.2, 2), voice(1.2, 3)), voiceprint=enrolled(1)))


def test_a_cluster_too_short_to_embed_is_not_compared(monkeypatch):
    brief = [Segment(0.0, 1.9, 0), Segment(1.9, 2.4, 1)]  # the second voice has only 0.5 s
    trial = Trial(monkeypatch, brief)
    assert kinds(trial.window(pad(voice(1.9, 1), voice(0.5, 2)), voiceprint=enrolled(1))) == []


# ---- the speaker model is required --------------------------------------------------------------

def test_a_missing_speaker_model_reports_model_unavailable_never_a_clean_audio_verdict(monkeypatch):
    trial = Trial(monkeypatch, SkillMatchException(statuscode=503, message="no models"))
    result = trial.window(pad(voice(2.4)))
    assert kinds(result) == ["MODEL_UNAVAILABLE"]


def test_an_unexpected_diarization_failure_also_fails_closed(monkeypatch):
    trial = Trial(monkeypatch, RuntimeError("boom"))
    assert "MODEL_UNAVAILABLE" in kinds(trial.window(pad(voice(2.4))))


def test_the_extractor_missing_while_comparing_clusters_fails_closed(monkeypatch):
    trial = Trial(monkeypatch, TWO_SPEAKERS)
    trial.extractor.fail = vp.SpeakerModelUnavailable("missing")
    assert "MODEL_UNAVAILABLE" in kinds(trial.window(pad(voice(1.2, 1), voice(1.2, 2)), voiceprint=enrolled(1)))


def test_silence_needs_no_speaker_model(monkeypatch):
    trial = Trial(monkeypatch, RuntimeError("never called"))
    assert kinds(trial.window(pad(silence(2.4)))) == []
    assert trial.diarized_lengths == []


# ---- BACKGROUND_AUDIO (device playback without speech) ---------------------------------------------

def test_a_sustained_tone_above_the_floor_is_background_audio(monkeypatch):
    trial = Trial(monkeypatch)
    result = trial.window(pad(tone(2.4)))
    assert kinds(result) == ["BACKGROUND_AUDIO"] and result["speech_detected"] is False


def test_a_tone_below_the_floor_is_not(monkeypatch):
    assert kinds(Trial(monkeypatch).window(pad(tone(2.4, amplitude=0.012)))) == []


def test_a_tone_shorter_than_two_seconds_is_not(monkeypatch):
    assert kinds(Trial(monkeypatch).window(pad(tone(1.9)))) == []


def test_the_calibrated_ambient_floor_raises_the_bar(monkeypatch):
    noisy_room = {**enrolled(1), "ambient_rms": 0.02}  # a tone of RMS 0.021 is just the room
    assert kinds(Trial(monkeypatch).window(pad(tone(2.4)), voiceprint=noisy_room)) == []
    quiet_room = {**enrolled(1), "ambient_rms": 0.003}
    assert kinds(Trial(monkeypatch).window(pad(tone(2.4)), voiceprint=quiet_room)) == ["BACKGROUND_AUDIO"]


def test_a_tone_split_over_two_windows_adds_up(monkeypatch):
    trial = Trial(monkeypatch)
    assert kinds(trial.window(pad(silence(0.9), tone(1.5)))) == []
    assert kinds(trial.window(pad(tone(1.0)))) == ["BACKGROUND_AUDIO"]  # 1.5 s + 1.0 s without a break


def test_silence_between_two_tones_breaks_the_run(monkeypatch):
    trial = Trial(monkeypatch)
    trial.window(pad(silence(0.9), tone(1.5)))
    assert kinds(trial.window(pad(silence(0.5), tone(1.0)))) == []


def test_very_loud_audio_stays_high_noise_only(monkeypatch):
    result = Trial(monkeypatch).window(pad(np.where(np.arange(38_400) % 2 == 0, 0.25, -0.25).astype(np.float32)))
    assert kinds(result) == ["HIGH_NOISE"]


def test_speech_is_not_background_audio(monkeypatch):
    trial = Trial(monkeypatch, [Segment(0.0, 2.4, 0)])
    assert "BACKGROUND_AUDIO" not in kinds(trial.window(pad(voice(2.4))))


def test_the_new_incident_kinds_are_audiovisual_not_browser_reported():
    from app.services.browser_supervision_service import AV_KINDS, BROWSER_KINDS

    for kind in ("VOICE_MISMATCH", "VOICE_UNVERIFIED", "LIP_SYNC_MISMATCH", "BACKGROUND_AUDIO"):
        assert kind in AV_KINDS and kind not in BROWSER_KINDS
