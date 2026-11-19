from __future__ import annotations

from typing import Any

import pytest

from ml.train.train_models import train_and_evaluate_level_classifier

_FEATURES: dict[str, Any] = {
    "total_touches": 20,
    "max_streak": 15,
    "touches_per_minute": 50.0,
    "regularity_score": 0.75,
    "mean_height_diameters": 1.6,
    "drops_count": 1,
}


def _row(participant_id: str, split: str, level_idx: int) -> dict[str, Any]:
    return {
        "sample_id": f"{participant_id}-{split}",
        "participant_id": participant_id,
        "split": split,
        "level_label": "Principiante",
        "level_idx": level_idx,
        "features": dict(_FEATURES),
    }


def test_same_participant_in_train_and_test_raises_clear_value_error() -> None:
    """
    A mislabeled dataset where the same participant_id was assigned to both the
    train and test split (e.g. every upload defaulted to the same auto-generated
    anon-p01 id) must fail with a descriptive ValueError, never a bare
    AssertionError that crashes the Celery worker with no actionable message.
    """
    dataset = [
        _row("anon-p01", "train", 0),
        _row("anon-p01", "test", 0),
        _row("anon-p02", "train", 1),
    ]

    with pytest.raises(ValueError, match="anon-p01"):
        train_and_evaluate_level_classifier(dataset=dataset, seed=1)
