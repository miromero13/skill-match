"""Best-effort diarization policy through the engine's calibration profile; mocked segments are not accuracy evidence.

Rewritten in T9: the old ``CalibrationSpeakerService.assess`` policy no longer exists (``CalibrationProfile.speech`` over
``AudioAnalyzer`` is the one implementation); the same three rejections and the same messages are asserted there.
"""
import numpy as np
import pytest

from app.services.integrity import messages as m, thresholds as t
from app.services.integrity.audio_analyzer import AudioAnalyzer
from app.services.integrity.calibration import CalibrationProfile
from app.services.integrity.state import InMemoryStateStore
from audio_fixtures import LevelExtractor, Segment, install_fake_vad, silence, voice


def speech_checks(monkeypatch, segments):
    install_fake_vad(monkeypatch)
    phrase = np.concatenate([voice(3.0), silence(5.0)])  # 8 s: a phrase and the pause
    analyzer = AudioAnalyzer(InMemoryStateStore(), speaker_segments=lambda audio: segments,
                             extractor=LevelExtractor(), vad_floor=0.0, min_speaker_s=t.CAL_SPEAKER_MIN_DURATION_S)
    return CalibrationProfile().speech(analyzer.analyze(phrase), phrase)


@pytest.mark.parametrize("segments,check,message", [
    ([Segment(0.3, 1.6, 0), Segment(2, 3.5, 1)], "single_speaker", m.MORE_THAN_ONE_VOICE),
    ([Segment(0.3, 2, 0), Segment(1.5, 3, 1)], "no_overlap", m.OVERLAPPING_VOICES),
    ([], "single_speaker", m.SINGLE_VOICE_UNCONFIRMED),
])
def test_ambiguous_multiple_or_overlapping_speakers_never_approve(monkeypatch, segments, check, message):
    failed = [c for c in speech_checks(monkeypatch, segments) if not c.passed]
    assert [(c.name, c.reason, c.status) for c in failed] == [(check, message, 400)]


def test_one_sufficient_speaker_is_only_an_estimate_not_identity(monkeypatch):
    checks = speech_checks(monkeypatch, [Segment(0.3, 2.2, 0)])
    assert all(c.passed for c in checks) and {"single_speaker", "no_overlap"} <= {c.name for c in checks}


def test_a_diarization_that_cannot_run_fails_closed_with_503(monkeypatch):
    def broken(_audio):
        raise RuntimeError("no models")

    install_fake_vad(monkeypatch)
    phrase = np.concatenate([voice(3.0), silence(5.0)])
    analyzer = AudioAnalyzer(InMemoryStateStore(), speaker_segments=broken, extractor=LevelExtractor(), vad_floor=0.0)
    failed = [c for c in CalibrationProfile().speech(analyzer.analyze(phrase), phrase) if not c.passed]
    assert [(c.name, c.status, c.reason) for c in failed] == [("single_speaker", 503, m.SPEAKER_MODELS_UNAVAILABLE)]


def test_missing_speaker_models_fail_closed(monkeypatch, tmp_path):
    import app.services.calibration_speaker_service as module
    from app.core.exceptions import SkillMatchException
    monkeypatch.setattr(module, "SEGMENTATION_MODEL", tmp_path / "missing.onnx")
    with pytest.raises(SkillMatchException) as caught:
        module.CalibrationSpeakerService.segments(np.zeros(128000, dtype=np.float32))
    assert caught.value.statuscode == 503
    assert caught.value.message == "Los modelos locales de hablantes no están disponibles."
