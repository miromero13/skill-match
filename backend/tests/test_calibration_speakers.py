"""Best-effort diarization policy; mocked segments are not accuracy evidence."""
from types import SimpleNamespace

import numpy as np
import pytest
from app.core.exceptions import SkillMatchException


def segment(start, end, speaker):
    return SimpleNamespace(start=start, end=end, speaker=speaker)


@pytest.mark.parametrize("segments,message", [
    ([segment(0.3, 1.6, 0), segment(2, 3.5, 1)], "Se detectaron indicios de más de una voz. Pausá llamadas y conversaciones y repetí la comprobación."),
    ([segment(0.3, 2, 0), segment(1.5, 3, 1)], "Se detectaron indicios de voces superpuestas. Buscá un ambiente sin conversaciones y repetí la comprobación."),
    ([], "No se pudo confirmar una sola voz con suficiente evidencia. Repetí la frase con voz clara."),
])
def test_ambiguous_multiple_or_overlapping_speakers_never_approve(monkeypatch, segments, message):
    from app.services.calibration_speaker_service import CalibrationSpeakerService
    monkeypatch.setattr(CalibrationSpeakerService, "segments", staticmethod(lambda audio: segments))
    with pytest.raises(SkillMatchException) as caught:
        CalibrationSpeakerService.assess(np.zeros(128000, dtype=np.float32))
    assert caught.value.statuscode == 400
    assert caught.value.message == message


def test_one_sufficient_speaker_is_only_an_estimate_not_identity(monkeypatch):
    from app.services.calibration_speaker_service import CalibrationSpeakerService
    monkeypatch.setattr(CalibrationSpeakerService, "segments", staticmethod(lambda audio: [segment(0.3, 2.2, 0)]))
    assert CalibrationSpeakerService.assess(np.zeros(128000, dtype=np.float32)) == {"single_speaker": True, "no_overlap": True}


def test_missing_speaker_models_fail_closed(monkeypatch, tmp_path):
    import app.services.calibration_speaker_service as module
    monkeypatch.setattr(module, "SEGMENTATION_MODEL", tmp_path / "missing.onnx")
    with pytest.raises(SkillMatchException) as caught:
        module.CalibrationSpeakerService.assess(np.zeros(128000, dtype=np.float32))
    assert caught.value.statuscode == 503
    assert caught.value.message == "Los modelos locales de hablantes no están disponibles."
