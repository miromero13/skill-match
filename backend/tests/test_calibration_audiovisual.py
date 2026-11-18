"""Synthetic timing policy tests; not real-device/lip-reading efficacy evidence."""
from types import SimpleNamespace

import numpy as np
import pytest
from app.core.exceptions import SkillMatchException


def evidence():
    return [SimpleNamespace(time_ms=index * 100, image="mock-jpeg") for index in range(80)]


def activity(pause=False):
    return [(index * 0.03 + 0.015, 1 <= index * 0.03 < 3 or (pause and 5 <= index * 0.03 < 6)) for index in range(266)]


@pytest.mark.parametrize("moving,message", [
    (lambda t: False, "Se detectó voz sin movimiento de boca coincidente. Repetí mirando a cámara y hablando solo cuando se indique."),
    (lambda t: 5 <= t < 7, "Se detectó voz sin movimiento de boca coincidente. Repetí mirando a cámara y hablando solo cuando se indique."),
])
def test_voice_without_corresponding_mouth_activity_rejects(monkeypatch, moving, message):
    from app.services.calibration_av_service import CalibrationAVService
    monkeypatch.setattr(CalibrationAVService, "voice_activity", staticmethod(lambda audio: activity()))
    monkeypatch.setattr(CalibrationAVService, "mouth_trace", staticmethod(lambda frames, enrollment: [(i * .1, .04 if moving(i * .1) else 0) for i in range(1, 80)]))
    with pytest.raises(SkillMatchException) as caught:
        CalibrationAVService.assess(evidence(), np.zeros(128000, dtype=np.float32), "enrollment")
    assert caught.value.statuscode == 400 and caught.value.message == message


def test_synchronized_motion_and_voice_can_pass_but_does_not_prove_words(monkeypatch):
    from app.services.calibration_av_service import CalibrationAVService
    monkeypatch.setattr(CalibrationAVService, "voice_activity", staticmethod(lambda audio: activity()))
    monkeypatch.setattr(CalibrationAVService, "mouth_trace", staticmethod(lambda frames, enrollment: [(i * .1, .04 if 1 <= i * .1 < 3 else 0) for i in range(1, 80)]))
    assert CalibrationAVService.assess(evidence(), np.zeros(128000, dtype=np.float32), "enrollment") == {"mouth_audio_sync": True, "speech_pause": True}


def test_speech_during_requested_pause_never_approves(monkeypatch):
    from app.services.calibration_av_service import CalibrationAVService
    monkeypatch.setattr(CalibrationAVService, "voice_activity", staticmethod(lambda audio: activity(pause=True)))
    with pytest.raises(SkillMatchException) as caught:
        CalibrationAVService.assess(evidence(), np.zeros(128000, dtype=np.float32), "enrollment")
    assert caught.value.statuscode == 400
    assert caught.value.message == "Se detectó voz durante la pausa. Guardá silencio cuando termine la frase y pausá llamadas o conversaciones."


def test_sparse_or_old_video_cannot_substitute_spoken_video():
    from app.services.calibration_av_service import CalibrationAVService
    for frames in (evidence()[:12], evidence()[::5], list(reversed(evidence()))):
        with pytest.raises(SkillMatchException) as caught:
            CalibrationAVService.assess(frames, np.zeros(128000, dtype=np.float32), "enrollment")
        assert caught.value.statuscode == 400
        assert caught.value.message == "No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación."
