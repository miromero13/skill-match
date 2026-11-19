"""T8 / S11: the enrollment rules without HTTP (fake models)."""
import numpy as np
import pytest

from app.services.integrity import audio_analyzer, enrollment
from app.services.integrity import voiceprint as vp
from audio_fixtures import LevelExtractor, Segment, SR, install_fake_vad, mouth_samples, silence, speaking, syllables

AMBIENT_MS = 1000


def mouth_of(env, **kw):
    return [(s.t_ms + AMBIENT_MS, s.mouth_open) for s in mouth_samples(env, **kw)]


@pytest.fixture(autouse=True)
def fake_vad(monkeypatch):
    install_fake_vad(monkeypatch)


def run(audio, mouth, segments=None, extractor=None, server=None):
    provider = segments or (lambda a: [Segment(0.0, len(a) / SR, 0)])
    return enrollment.enroll_voice(
        audio, AMBIENT_MS, mouth, mouth if server is None else server, analyzer=audio_analyzer.AudioAnalyzer(
            enrollment.InMemoryStateStore(), speaker_segments=provider, extractor=extractor or LevelExtractor()),
        extractor=extractor or LevelExtractor())


def phrase(seconds=4.0, seed=3):
    env = syllables(seed, chunks=int(seconds * 1000 / 30))
    return np.concatenate([silence(1.0), speaking(env)]), env


def test_a_clean_recording_yields_a_record_with_the_ambient_floor():
    audio, env = phrase()
    record = run(audio, mouth_of(env))
    assert record["voiced_s"] >= 3.0 and record["ambient_rms"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("code,build", [
    ("INSUFFICIENT_SPEECH", lambda: (phrase(2.0)[0], mouth_of(phrase(2.0)[1]))),
    ("UNSYNCED", lambda: (phrase()[0], mouth_of(phrase()[1], still=True))),
    ("NO_MOUTH", lambda: (phrase()[0], [])),
])
def test_rejections_carry_a_code(code, build):
    audio, mouth = build()
    with pytest.raises(enrollment.EnrollmentError) as error:
        run(audio, mouth)
    assert error.value.code == code


def test_a_recording_shorter_than_its_silence_segment_is_insufficient():
    with pytest.raises(enrollment.EnrollmentError) as error:
        enrollment.enroll_voice(silence(0.5), AMBIENT_MS, [], [])
    assert error.value.code == "INSUFFICIENT_SPEECH"


def test_overlapping_or_several_voices_are_rejected_before_any_embedding():
    audio, env = phrase()
    extractor = LevelExtractor()
    with pytest.raises(enrollment.EnrollmentError) as error:
        run(audio, mouth_of(env), segments=lambda a: [Segment(0.0, 2.0, 0), Segment(1.0, 3.0, 1)], extractor=extractor)
    assert error.value.code == "MULTIPLE_SPEAKERS" and extractor.calls == []


def test_a_missing_model_raises_unavailable():
    audio, env = phrase()
    extractor = LevelExtractor()
    extractor.fail = vp.SpeakerModelUnavailable("missing")
    with pytest.raises(vp.SpeakerModelUnavailable):
        run(audio, mouth_of(env), extractor=extractor)

    def broken(_audio):
        raise RuntimeError("no diarization models")

    with pytest.raises(vp.SpeakerModelUnavailable):
        run(audio, mouth_of(env), segments=broken)


# ---- T9 / S11: the browser's mouth telemetry must agree with the frames the server measured --------------------


def test_telemetry_that_contradicts_the_server_frames_rejects_the_enrollment():
    audio, env = phrase()
    mouth = mouth_of(env)
    wrong = [(at, value + 0.6) for at, value in mouth]  # the server saw a very different aperture on every frame
    with pytest.raises(enrollment.EnrollmentError) as error:
        run(audio, mouth, server=wrong)
    assert error.value.code == "UNTRUSTED_TELEMETRY"


def test_telemetry_that_the_server_frames_cannot_verify_rejects_the_enrollment():
    audio, env = phrase()
    mouth = mouth_of(env)
    for server in ([], mouth[:3], [(at + 5000, value) for at, value in mouth]):  # none, too few, never at the same time
        with pytest.raises(enrollment.EnrollmentError) as error:
            run(audio, mouth, server=server)
        assert error.value.code == "UNTRUSTED_TELEMETRY"


def test_telemetry_with_occasional_noise_is_still_trusted():
    audio, env = phrase()
    mouth = mouth_of(env)
    server = [(at, value + (0.5 if index % 10 == 0 else 0.0)) for index, (at, value) in enumerate(mouth)]  # 10 % off
    assert run(audio, mouth, server=server)["voiced_s"] >= 3.0


def test_the_server_frames_are_mandatory_for_an_enrollment():
    """T9b: ``server_mouth`` has no default any more, and empty server evidence is untrusted telemetry."""
    import inspect
    assert inspect.signature(enrollment.enroll_voice).parameters["server_mouth"].default is inspect.Parameter.empty
    audio, env = phrase()
    with pytest.raises(enrollment.EnrollmentError) as error:
        run(audio, mouth_of(env), server=[])
    assert error.value.code == "UNTRUSTED_TELEMETRY"
