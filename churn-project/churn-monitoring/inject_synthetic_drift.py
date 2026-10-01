"""
inject_synthetic_drift.py

Phase 5, step 2: validate the drift monitor itself, per the spec - "inject
synthetic drift and confirm alerts fire" is what a "drift-alert accuracy"
number actually requires demonstrating, not just having a dashboard.

Takes the latest feature snapshot, deliberately shifts a random subset of
features far outside their training-baseline range, re-runs the same PSI
computation drift_monitor.py uses, and checks:
  - recall: of the features we perturbed, how many got flagged?
  - specificity: of the features we left alone, how many correctly did NOT
    get flagged?
  - accuracy: (true positives + true negatives) / total features - this is
    the number written to data/drift_validation.json and folded into
    ../churn-outcomes/evaluate.py's "drift alert accuracy" metric.

Run:
  python inject_synthetic_drift.py
"""

import json
import os

import numpy as np
import pandas as pd

from drift_monitor import BASELINE_PATH, FEATURES_PATH, compute_feature_psi

RNG = np.random.default_rng(11)
DATA_DIR = "data"
N_PERTURBED = 5
SHIFT_STD_MULTIPLIER = 6.0  # shift by this many training std-devs


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    feat = pd.read_csv(FEATURES_PATH)
    feat["as_of_date"] = feat["as_of_date"].astype(str)
    as_of = sorted(feat["as_of_date"].unique())[-1]
    current_df = feat[feat["as_of_date"] == as_of].copy()

    with open(BASELINE_PATH) as f:
        baseline_doc = json.load(f)
    baseline = baseline_doc["baseline"]

    all_features = [f for f in baseline if f in current_df.columns]
    perturbed = list(RNG.choice(all_features, size=min(N_PERTURBED, len(all_features)), replace=False))
    untouched = [f for f in all_features if f not in perturbed]

    perturbed_df = current_df.copy()
    for feature in perturbed:
        std = baseline[feature]["std"] or 1.0
        shift = SHIFT_STD_MULTIPLIER * (std if std > 0 else 1.0)
        # Half the perturbed features shift up, half down - alerts should
        # fire either way since PSI is direction-agnostic.
        direction = 1 if RNG.random() < 0.5 else -1
        perturbed_df[feature] = perturbed_df[feature].fillna(baseline[feature]["mean"]) + direction * shift

    feature_psi = compute_feature_psi(perturbed_df, baseline_doc)

    true_positives = sum(1 for f in perturbed if feature_psi.get(f, {}).get("alert"))
    true_negatives = sum(1 for f in untouched if not feature_psi.get(f, {}).get("alert"))
    false_negatives = len(perturbed) - true_positives
    false_positives = len(untouched) - true_negatives

    recall = true_positives / len(perturbed) if perturbed else float("nan")
    specificity = true_negatives / len(untouched) if untouched else float("nan")
    accuracy = (true_positives + true_negatives) / len(all_features)

    report = {
        "as_of_date": as_of,
        "perturbed_features": perturbed,
        "untouched_features": untouched,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "recall": recall,
        "specificity": specificity,
        "drift_alert_accuracy": accuracy,
        "detail": feature_psi,
    }
    with open(f"{DATA_DIR}/drift_validation.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Injected drift into {perturbed}")
    print(f"  recall={recall:.2f} specificity={specificity:.2f} accuracy={accuracy:.2f}")
    print(f"Wrote {DATA_DIR}/drift_validation.json")


if __name__ == "__main__":
    main()
