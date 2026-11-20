"""S6: tolerant, view-robust replication score of a user signature against a reference signature."""
from __future__ import annotations

import json

import pytest

from app.skill_validation import similarity
from tests.skill_validation import synthetic as syn

D_FULL, D_ZERO = similarity.DEFAULT_D_FULL, similarity.DEFAULT_D_ZERO


def score(reference: dict, user: dict) -> similarity.Comparison:
    return similarity.compare_sequences(similarity.parse_pose(reference), similarity.parse_pose(user))


@pytest.fixture(scope="module")
def juggle_ref() -> dict:
    return syn.signature(syn.juggle, seconds=6, cycle_seconds=2.0, noise_deg=2, seed=1)


def test_identical_motion_scores_100(juggle_ref):
    result = score(juggle_ref, juggle_ref)
    assert result.ok
    assert result.distance == pytest.approx(0.0, abs=1e-6)
    assert result.score(D_FULL, D_ZERO) == pytest.approx(100.0)


def test_same_motion_other_person_noise_scores_100(juggle_ref):
    user = syn.signature(syn.juggle, seconds=6, cycle_seconds=2.0, noise_deg=4, seed=7)
    assert score(juggle_ref, user).score(D_FULL, D_ZERO) >= 95


@pytest.mark.parametrize("cycle_seconds", [1.2, 3.0, 3.8])
def test_slower_or_faster_tempo_still_scores_high(juggle_ref, cycle_seconds):
    user = syn.signature(syn.juggle, seconds=6 * cycle_seconds / 2.0, cycle_seconds=cycle_seconds, noise_deg=2, seed=3)
    result = score(juggle_ref, user)
    assert result.score(D_FULL, D_ZERO) >= 90, result.detail()


def test_mirrored_performance_scores_high_and_is_flagged(juggle_ref):
    user = syn.signature(syn.mirrored(syn.juggle), seconds=6, cycle_seconds=2.0, noise_deg=2, seed=4)
    result = score(juggle_ref, user)
    assert result.mirrored is True
    assert result.score(D_FULL, D_ZERO) >= 95


def test_other_camera_angle_is_invariant(juggle_ref):
    user = syn.signature(syn.juggle, seconds=6, cycle_seconds=2.0, noise_deg=2, seed=1, view_yaw_deg=40)
    assert score(juggle_ref, user).score(D_FULL, D_ZERO) >= 99


def test_idle_lead_in_is_trimmed_and_repeated_cycles_match(juggle_ref):
    user = syn.signature(syn.juggle, seconds=14, cycle_seconds=2.0, noise_deg=2, seed=5, lead_in_seconds=4)
    result = score(juggle_ref, user)
    assert result.coverage == pytest.approx(1.0)
    assert result.score(D_FULL, D_ZERO) >= 95


def test_missing_frames_are_tolerated(juggle_ref):
    user = syn.signature(syn.juggle, seconds=6, cycle_seconds=2.0, noise_deg=2, seed=6, missing_every=4)
    assert score(juggle_ref, user).score(D_FULL, D_ZERO) >= 90


@pytest.mark.parametrize(
    ("reference_motion", "user_motion"),
    [
        (syn.juggle, syn.jumping_jack),
        (syn.squat, syn.juggle),
        (syn.squat, syn.jumping_jack),
        (syn.jumping_jack, syn.right_arm_wave),
        (syn.right_arm_wave, syn.squat),
    ],
)
def test_different_motion_scores_low(reference_motion, user_motion):
    reference = syn.signature(reference_motion, seconds=6, noise_deg=2, seed=1)
    user = syn.signature(user_motion, seconds=6, noise_deg=2, seed=2)
    assert score(reference, user).score(D_FULL, D_ZERO) < 40


def test_partially_similar_motion_gets_at_most_partial_credit():
    # Both raise the right leg, but a squat also bends the other leg, the trunk and the arms.
    reference = syn.signature(syn.juggle, seconds=6, noise_deg=2, seed=1)
    user = syn.signature(syn.squat, seconds=6, noise_deg=2, seed=2)
    assert score(reference, user).score(D_FULL, D_ZERO) < 60


@pytest.mark.parametrize("motion", [syn.juggle, syn.squat, syn.jumping_jack])
def test_static_user_against_moving_reference_scores_low(motion):
    reference = syn.signature(motion, seconds=6, noise_deg=2, seed=1)
    user = syn.signature(syn.static, seconds=6, noise_deg=2, seed=2)
    result = score(reference, user)
    assert result.motion_factor < 0.5
    assert result.score(D_FULL, D_ZERO) < 20


def test_agitated_user_against_static_reference_scores_low():
    reference = syn.signature(syn.static, seconds=6, noise_deg=1, seed=1)
    user = syn.signature(syn.jumping_jack, seconds=6, noise_deg=2, seed=2)
    assert score(reference, user).score(D_FULL, D_ZERO) < 20


def test_partial_replication_is_penalized_by_coverage():
    reference = syn.signature(syn.squat, seconds=10, cycle_seconds=10, noise_deg=2, seed=1)
    user = syn.signature(syn.squat, seconds=2.5, cycle_seconds=10, noise_deg=2, seed=2)
    result = score(reference, user)
    assert result.coverage < 0.5
    assert result.score(D_FULL, D_ZERO) < 70


def test_short_user_clip_of_a_cyclic_reference_keeps_full_coverage():
    reference = syn.signature(syn.juggle, seconds=40, cycle_seconds=2.0, noise_deg=2, seed=1)
    user = syn.signature(syn.juggle, seconds=6, cycle_seconds=2.0, noise_deg=2, seed=2)
    result = score(reference, user)
    assert result.coverage == pytest.approx(1.0)
    assert result.score(D_FULL, D_ZERO) >= 95


def test_too_few_user_frames_is_not_ok(juggle_ref):
    user = syn.signature(syn.juggle, seconds=0.5, noise_deg=2, seed=2)
    result = score(juggle_ref, user)
    assert result.ok is False and result.reason == "user"
    assert result.score(D_FULL, D_ZERO) == 0.0


def test_tolerance_curve_is_generous_and_monotonic():
    values = [similarity.tolerance_score(d, D_FULL, D_ZERO) for d in range(0, 40)]
    assert values[0] == 100.0 and values[int(D_FULL)] == 100.0 and values[-1] == 0.0
    assert all(a >= b for a, b in zip(values, values[1:]))


def test_sixty_second_signature_is_compact():
    pose = syn.signature(syn.juggle, seconds=60, noise_deg=3, seed=1)
    assert pose["frames_sampled"] == 600
    assert len(json.dumps(pose, allow_nan=False)) < 200_000
