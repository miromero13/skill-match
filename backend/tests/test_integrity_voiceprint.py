"""T8 / S3, S11: voiceprint embedding, matching and enrollment rules, with an injected fake extractor.

The fake derives an embedding from the audio level, so "speakers" are constant-level signals: the logic under
test (minimum speech, normalization, averaging, consistency, thresholds) never needs a real model.
"""
import numpy as np
import pytest

from app.services.integrity import thresholds as t
from app.services.integrity import voiceprint as vp

SR = 16_000


def speaker(level, seconds):
    return np.full(int(seconds * SR), level, dtype=np.float32)


class FakeExtractor:
    """Speaker ``k`` (audio level k/100) is the unit vector e_k plus a little of e_0 to keep it deterministic."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def embed(self, audio):
        if self.fail:
            raise self.fail
        self.calls.append(len(audio))
        level = int(round(float(np.mean(audio)) * 100))
        vec = np.zeros(16, dtype=np.float32)
        vec[level % 16] = 3.0  # not unit length on purpose: normalization is the module's job
        return vec


def test_l2_normalize_and_cosine():
    unit = vp.l2_normalize(np.array([3.0, 4.0]))
    assert float(np.linalg.norm(unit)) == pytest.approx(1.0)
    assert vp.cosine(np.array([1.0, 0.0]), np.array([2.0, 0.0])) == pytest.approx(1.0)
    assert vp.cosine(np.array([1.0, 0.0]), np.array([0.0, 5.0])) == pytest.approx(0.0)
    assert vp.cosine(np.array([1.0, 0.0]), np.array([-1.0, 0.0])) == pytest.approx(-1.0)
    assert vp.cosine(np.zeros(2), np.array([1.0, 0.0])) == 0.0  # a degenerate vector matches nothing


def test_enrollment_averages_segments_into_one_normalized_embedding():
    record = vp.enroll(FakeExtractor(), speaker(0.03, 4.5), ambient_rms=0.004)
    embedding = vp.embedding_of(record)
    assert float(np.linalg.norm(embedding)) == pytest.approx(1.0)
    assert vp.cosine(embedding, vp.l2_normalize(np.eye(16, dtype=np.float32)[3])) == pytest.approx(1.0)
    assert record["ambient_rms"] == pytest.approx(0.004)
    assert record["voiced_s"] == pytest.approx(4.5)
    assert record["version"] == vp.RECORD_VERSION


def test_enrollment_with_too_little_speech_is_insufficient_and_never_embeds():
    extractor = FakeExtractor()
    with pytest.raises(vp.EnrollmentError) as error:
        vp.enroll(extractor, speaker(0.03, t.VOICEPRINT_MIN_ENROLL_VOICED_S - 0.1), ambient_rms=0.004)
    assert error.value.code == "INSUFFICIENT_SPEECH"
    assert extractor.calls == []


def test_enrollment_rejects_segments_that_are_not_one_voice():
    mixed = np.concatenate([speaker(0.03, 2.0), speaker(0.05, 2.0)])
    with pytest.raises(vp.EnrollmentError) as error:
        vp.enroll(FakeExtractor(), mixed, ambient_rms=0.004)
    assert error.value.code == "INCONSISTENT"


def test_enrollment_without_the_model_fails_closed():
    with pytest.raises(vp.SpeakerModelUnavailable):
        vp.enroll(FakeExtractor(fail=vp.SpeakerModelUnavailable("missing")), speaker(0.03, 4.0), ambient_rms=0.0)


def test_match_same_speaker_different_speaker_and_insufficient():
    record = vp.enroll(FakeExtractor(), speaker(0.03, 4.0), ambient_rms=0.004)
    extractor = FakeExtractor()
    same = vp.match_voice(extractor, record, speaker(0.03, 1.5))
    assert (same.status, round(same.similarity, 3)) == ("match", 1.0)
    other = vp.match_voice(extractor, record, speaker(0.07, 1.5))
    assert other.status == "mismatch" and other.similarity == pytest.approx(0.0)
    calls = len(extractor.calls)
    short = vp.match_voice(extractor, record, speaker(0.03, t.VOICEPRINT_MIN_VERIFY_VOICED_S - 0.05))
    assert (short.status, short.similarity) == ("insufficient", None)
    assert len(extractor.calls) == calls  # no verdict and no inference below the minimum


def test_match_threshold_is_inclusive():
    record = {"version": vp.RECORD_VERSION, "embedding": [1.0, 0.0], "ambient_rms": 0.0, "voiced_s": 4.0}

    class Fixed:
        def __init__(self, vec):
            self.vec = np.asarray(vec, dtype=np.float64)

        def embed(self, _audio):
            return self.vec

    edge = [t.VOICEPRINT_MATCH_THRESHOLD, float(np.sqrt(1 - t.VOICEPRINT_MATCH_THRESHOLD ** 2))]
    assert vp.match_voice(Fixed(edge), record, speaker(0.0, 2.0)).status == "match"
    below = [t.VOICEPRINT_MATCH_THRESHOLD - 0.01, float(np.sqrt(1 - (t.VOICEPRINT_MATCH_THRESHOLD - 0.01) ** 2))]
    assert vp.match_voice(Fixed(below), record, speaker(0.0, 2.0)).status == "mismatch"


def test_match_without_the_model_raises_instead_of_a_clean_verdict():
    record = vp.enroll(FakeExtractor(), speaker(0.03, 4.0), ambient_rms=0.0)
    with pytest.raises(vp.SpeakerModelUnavailable):
        vp.match_voice(FakeExtractor(fail=vp.SpeakerModelUnavailable("missing")), record, speaker(0.03, 2.0))


def test_a_malformed_stored_voiceprint_is_rejected_not_trusted():
    for bad in (None, {}, {"embedding": []}, {"embedding": ["x"]}, {"embedding": [float("nan"), 1.0]}):
        with pytest.raises(vp.SpeakerModelUnavailable):
            vp.embedding_of(bad)


def test_the_default_extractor_without_the_pinned_model_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vp, "EMBEDDING_MODEL", tmp_path / "absent.onnx")
    with pytest.raises(vp.SpeakerModelUnavailable):
        vp.SherpaEmbeddingExtractor().embed(speaker(0.03, 2.0))


def test_the_default_extractor_refuses_a_model_that_fails_its_pin(monkeypatch, tmp_path):
    fake = tmp_path / "speaker_embedding.onnx"
    fake.write_bytes(b"not the pinned model")
    monkeypatch.setattr(vp, "EMBEDDING_MODEL", fake)
    with pytest.raises(vp.SpeakerModelUnavailable):
        vp.SherpaEmbeddingExtractor().embed(speaker(0.03, 2.0))


@pytest.mark.skipif(not vp.model_available(), reason="pinned speaker_embedding.onnx is not installed")
def test_real_model_smoke_two_different_signals_do_not_crash():
    extractor = vp.SherpaEmbeddingExtractor()
    tone = (0.3 * np.sin(2 * np.pi * 200 * np.arange(3 * SR) / SR)).astype(np.float32)
    noise = np.random.default_rng(0).normal(0, 0.1, 3 * SR).astype(np.float32)
    first, second = extractor.embed(tone), extractor.embed(noise)
    assert first.shape == second.shape == (512,)
    assert np.all(np.isfinite(first)) and np.all(np.isfinite(second))
    assert -1.0 <= vp.cosine(first, second) <= 1.0
