from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.football.pipeline.scoring import LEVELS, RuleBasedLevelClassifier

FEATURE_NAMES: list[str] = [
    "total_touches",
    "max_streak",
    "touches_per_minute",
    "regularity_score",
    "mean_height_diameters",
    "horizontal_displacement_diameters",
    "drops_count",
    "mean_challenge_compliance",
    "av_coherence",
]

# Neutral defaults for features a bare juggling clip cannot measure (no challenge
# timing, no audio): used only to impute missing keys so real samples without
# these features can still train, instead of raising KeyError or inventing a
# fixed value inside the feature extractor itself.
_FEATURE_DEFAULTS: dict[str, float] = {
    "horizontal_displacement_diameters": 1.5,
    "mean_challenge_compliance": 1.0,
    "av_coherence": 1.0,
}


def _feature_vector(features: dict[str, Any]) -> list[float]:
    return [
        float(features[f]) if f in features else _FEATURE_DEFAULTS[f]
        for f in FEATURE_NAMES
    ]


def generate_grouped_participant_dataset(
    num_participants: int = 32,
    clips_per_participant: int = 4,
    seed: int = 2026,
) -> list[dict[str, Any]]:
    """
    Generate a synthetic multi-participant dataset with realistic multi-dimensional
    skill profiles where true level depends on a combination of streak, cadence
    (touches/min), regularity, challenge compliance, lateral control, and drops.
    Splits are assigned strictly by `participant_id` (zero participant leakage).
    """
    rng = np.random.default_rng(seed)
    samples: list[dict[str, Any]] = []

    for p_idx in range(num_participants):
        participant_id = f"P-{p_idx:03d}"
        split = "train" if p_idx < int(num_participants * 0.7) else "test"
        true_level_idx = p_idx % 4
        true_level = LEVELS[true_level_idx]

        for c_idx in range(clips_per_participant):
            # Include boundary / borderline streak cases where single-feature rules struggle
            # but multi-feature trained classifier succeeds using cadence + regularity + compliance
            if true_level_idx == 0:  # Principiante
                max_streak = int(rng.integers(3, 10))
                total_touches = max_streak + int(rng.integers(0, 4))
                tpm = float(rng.uniform(14.0, 28.0))
                reg = float(rng.uniform(0.42, 0.65))
                comp = float(rng.uniform(0.45, 0.70))
                drops = int(rng.integers(2, 5))
                horiz = float(rng.uniform(1.8, 3.2))
            elif true_level_idx == 1:  # Intermedio
                max_streak = int(rng.integers(7, 28))
                total_touches = max_streak + int(rng.integers(2, 8))
                tpm = float(rng.uniform(30.0, 52.0))
                reg = float(rng.uniform(0.66, 0.80))
                comp = float(rng.uniform(0.70, 0.84))
                drops = int(rng.integers(1, 3))
                horiz = float(rng.uniform(1.1, 1.9))
            elif true_level_idx == 2:  # Avanzado
                max_streak = int(rng.integers(22, 64))
                total_touches = max_streak + int(rng.integers(4, 12))
                tpm = float(rng.uniform(55.0, 82.0))
                reg = float(rng.uniform(0.81, 0.91))
                comp = float(rng.uniform(0.84, 0.94))
                drops = int(rng.integers(0, 2))
                horiz = float(rng.uniform(0.6, 1.2))
            else:  # Experto
                max_streak = int(rng.integers(54, 95))
                total_touches = max_streak + int(rng.integers(5, 15))
                tpm = float(rng.uniform(85.0, 120.0))
                reg = float(rng.uniform(0.91, 0.98))
                comp = float(rng.uniform(0.92, 0.99))
                drops = 0
                horiz = float(rng.uniform(0.2, 0.65))

            samples.append(
                {
                    "sample_id": f"{participant_id}-C{c_idx:02d}",
                    "participant_id": participant_id,
                    "split": split,
                    "level_label": true_level,
                    "level_idx": true_level_idx,
                    "features": {
                        "total_touches": total_touches,
                        "max_streak": max_streak,
                        "touches_per_minute": round(tpm, 2),
                        "regularity_score": round(reg, 4),
                        "mean_height_diameters": round(
                            float(rng.uniform(1.3, 2.4)), 3
                        ),
                        "horizontal_displacement_diameters": round(horiz, 3),
                        "drops_count": drops,
                        "mean_challenge_compliance": round(comp, 4),
                        "av_coherence": round(float(rng.uniform(0.85, 0.99)), 4),
                    },
                }
            )

    return samples


def train_and_evaluate_level_classifier(
    dataset: list[dict[str, Any]] | None = None,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Train an L2-regularized multinomial logistic / ordinal classifier on the
    participant-grouped `train` split and evaluate against `RuleBasedLevelClassifier`
    on the unseen `test` participants.
    """
    data = dataset or generate_grouped_participant_dataset(seed=seed)
    train_rows = [r for r in data if r["split"] == "train"]
    test_rows = [r for r in data if r["split"] == "test"]

    # Verify zero participant overlap between train and test splits
    train_participants = {r["participant_id"] for r in train_rows}
    test_participants = {r["participant_id"] for r in test_rows}
    assert train_participants.isdisjoint(test_participants)

    x_train = np.array(
        [_feature_vector(r["features"]) for r in train_rows],
        dtype=np.float64,
    )
    y_train = np.array([int(r["level_idx"]) for r in train_rows], dtype=np.int64)

    scaler_mean = np.mean(x_train, axis=0)
    scaler_scale = np.maximum(1e-6, np.std(x_train, axis=0))
    x_train_norm = (x_train - scaler_mean) / scaler_scale

    num_classes = len(LEVELS)
    num_features = len(FEATURE_NAMES)
    weights = np.zeros((num_classes, num_features), dtype=np.float64)
    biases = np.zeros(num_classes, dtype=np.float64)

    y_onehot = np.eye(num_classes, dtype=np.float64)[y_train]
    lr = 0.25
    reg_lambda = 1e-3
    loss_history: list[dict[str, float]] = []

    for epoch in range(700):
        logits = x_train_norm @ weights.T + biases
        logits -= np.max(logits, axis=1, keepdims=True)
        exp_l = np.exp(logits)
        probs = exp_l / np.sum(exp_l, axis=1, keepdims=True)

        if epoch % 100 == 0 or epoch == 699:
            ce_loss = float(-np.mean(np.sum(y_onehot * np.log(probs + 1e-12), axis=1)))
            loss_history.append({"epoch": epoch, "loss": round(ce_loss, 4)})

        diff = (probs - y_onehot) / float(len(train_rows))
        grad_w = diff.T @ x_train_norm + reg_lambda * weights
        grad_b = np.sum(diff, axis=0)
        weights -= lr * grad_w
        biases -= lr * grad_b

    # Evaluate on unseen test participants
    rule_clf = RuleBasedLevelClassifier()
    rule_correct = 0
    trained_correct = 0
    trained_within_one = 0
    confusion_matrix = [[0 for _ in range(num_classes)] for _ in range(num_classes)]

    for row in test_rows:
        feats = row["features"]
        true_idx = int(row["level_idx"])

        rule_probs = rule_clf.predict_proba(feats)
        rule_pred_lvl = max(LEVELS, key=lambda l: rule_probs[l])
        if LEVELS.index(rule_pred_lvl) == true_idx:
            rule_correct += 1

        x_vec = (
            np.array(_feature_vector(feats), dtype=np.float64) - scaler_mean
        ) / scaler_scale
        t_logits = weights @ x_vec + biases
        pred_idx = int(np.argmax(t_logits))
        confusion_matrix[true_idx][pred_idx] += 1
        if pred_idx == true_idx:
            trained_correct += 1
        if abs(pred_idx - true_idx) <= 1:
            trained_within_one += 1

    n_test = max(1, len(test_rows))
    rule_acc = round(rule_correct / float(n_test), 4)
    trained_acc = round(trained_correct / float(n_test), 4)
    within_one_acc = round(trained_within_one / float(n_test), 4)

    return {
        "model_name": "level_classifier",
        "version": "1.0.0-onnx",
        "feature_names": FEATURE_NAMES,
        "classes": LEVELS,
        "scaler_mean": [round(float(v), 6) for v in scaler_mean],
        "scaler_scale": [round(float(v), 6) for v in scaler_scale],
        "weights": [
            [round(float(w), 6) for w in row_w] for row_w in weights
        ],
        "biases": [round(float(b), 6) for b in biases],
        "metrics": {
            "test_samples": n_test,
            "train_participants": len(train_participants),
            "test_participants": len(test_participants),
            "rule_baseline_accuracy": rule_acc,
            "trained_exact_accuracy": trained_acc,
            "trained_within_one_level_accuracy": within_one_acc,
            "beats_rule_baseline": trained_acc > rule_acc,
            "confusion_matrix": confusion_matrix,
            "loss_history": loss_history,
        },
    }


if __name__ == "__main__":
    artifact = train_and_evaluate_level_classifier()
    print(json.dumps(artifact["metrics"], indent=2))
