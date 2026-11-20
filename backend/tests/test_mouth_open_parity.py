"""T8 / S11: the mouth aperture score is one formula, shared with the browser (frontend/src/services/gaze-tracking.ts).

The same landmarks and expected numbers are pinned in frontend/src/test/gaze-tracking.test.ts.
"""
import numpy as np
import pytest

from app.services.integrity.gaze import mouth_open_score


def mouth(lip_gap):
    """478 landmarks: mouth corners (78, 308) 0.14 apart, inner lips (13 upper, 14 lower) ``lip_gap`` apart."""
    points = np.full((478, 3), 0.5)
    points[78] = (0.43, 0.65, 0.0)
    points[308] = (0.57, 0.65, 0.0)
    points[13] = (0.5, 0.65, 0.0)
    points[14] = (0.5, 0.65 + lip_gap, 0.0)
    return points


CASES = {
    "closed": (0.0, {}, 0.0),
    "inner_lip_ratio_only": (0.021, {}, 0.21),  # (0.021 / 0.14) * 1.4
    "jaw_open_softened_by_mouth_close": (0.0, {"jawOpen": 0.3, "mouthClose": 0.5}, 0.2175),  # 0.3 * (1 - 0.55 * 0.5)
    "mouth_close_never_below_a_fifth": (0.0, {"jawOpen": 0.4, "mouthClose": 1.0}, 0.18),  # 0.4 * 0.45
    "funnel_and_pucker": (0.0, {"mouthFunnel": 0.4, "mouthPucker": 0.2}, 0.275),  # (0.4 + 0.5 * 0.2) * 0.55
    "the_largest_signal_wins": (0.021, {"jawOpen": 0.4, "mouthClose": 1.0}, 0.21),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_mouth_open_score_cases(name):
    gap, blendshapes, expected = CASES[name]
    assert mouth_open_score(mouth(gap), blendshapes) == pytest.approx(expected, abs=1e-9)


def test_a_degenerate_mouth_is_closed_not_an_error():
    assert mouth_open_score(np.full((478, 3), 0.5), {}) == 0.0
