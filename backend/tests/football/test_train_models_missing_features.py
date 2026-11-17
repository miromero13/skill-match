from __future__ import annotations

from typing import Any

from ml.train.train_models import FEATURE_NAMES, train_and_evaluate_level_classifier


def _row(participant_id: str, split: str, level_idx: int, features: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": f"{participant_id}-sample",
        "participant_id": participant_id,
        "split": split,
        "level_label": "Principiante",
        "level_idx": level_idx,
        "features": features,
    }


def test_training_tolerates_rows_missing_unmeasured_real_features() -> None:
    """
    A real sample's features dict may omit horizontal_displacement_diameters,
    mean_challenge_compliance and av_coherence (unmeasurable from a bare clip,
    see training_service._extract_features_from_sample_clip). Training must
    impute a neutral default for the missing keys instead of raising KeyError.
    """
    base_features = {
        "total_touches": 20,
        "max_streak": 15,
        "touches_per_minute": 50.0,
        "regularity_score": 0.75,
        "mean_height_diameters": 1.6,
        "drops_count": 1,
    }
    assert set(base_features).isdisjoint(
        {"horizontal_displacement_diameters", "mean_challenge_compliance", "av_coherence"}
    )

    dataset = [
        _row(f"REAL-{i:02d}", "train" if i < 6 else "test", i % 4, dict(base_features))
        for i in range(8)
    ]

    artifact = train_and_evaluate_level_classifier(dataset=dataset, seed=7)

    assert artifact["feature_names"] == FEATURE_NAMES
    assert len(artifact["scaler_mean"]) == len(FEATURE_NAMES)
    assert artifact["metrics"]["test_samples"] == 2
