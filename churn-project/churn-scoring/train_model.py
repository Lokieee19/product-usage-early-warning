"""
train_model.py

Phase 2, step 1: train a baseline churn-risk model on top of the Phase 1
feature table (../churn-pipeline/data/features.csv), joined against the
latent-risk ground truth (../churn-pipeline/data/_latent_risk_labels.csv)
that exists only for training/eval, never as a feature.

Time-based split, not random: the most recent HOLDOUT_WEEKS snapshot
dates are held out entirely from training, so validation AUC reflects
"would this have ranked next week's risk correctly" rather than leaking
information across snapshots of the same account.

Run:
  python train_model.py
"""

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

FEATURES_PATH = "../churn-pipeline/data/features.csv"
LABELS_PATH = "../churn-pipeline/data/_latent_risk_labels.csv"
MODELS_DIR = "models"
HOLDOUT_WEEKS = 2

FEATURE_COLUMNS = [
    "logins_per_seat_trend_3m",
    "searches_per_seat_trend_3m",
    "inmail_sends_trend_3m",
    "pct_seats_active_30d",
    "crm_sync_active_30d",
    "avg_session_duration_trend",
    "inmail_response_rate",
    "support_tickets_90d",
    "support_csat",
    "champion_turnover_flag",
    "seat_utilization_vs_contracted",
    "days_to_renewal",
    "nps_last_survey",
]


def load_training_frame():
    feat = pd.read_csv(FEATURES_PATH)
    labels = pd.read_csv(LABELS_PATH)
    df = feat.merge(labels, on="account_id", how="inner")
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    df["label"] = df["_is_latent_risk"].astype(int)
    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def time_based_split(df):
    dates = sorted(df["as_of_date"].unique())
    if len(dates) <= HOLDOUT_WEEKS:
        raise ValueError(
            f"Need more than {HOLDOUT_WEEKS} snapshot dates for a time-based split, "
            f"got {len(dates)}. Backfill more history with feature_pipeline.py --backfill."
        )
    holdout_dates = dates[-HOLDOUT_WEEKS:]
    train_dates = dates[:-HOLDOUT_WEEKS]
    train_df = df[df["as_of_date"].isin(train_dates)]
    holdout_df = df[df["as_of_date"].isin(holdout_dates)]
    return train_df, holdout_df, train_dates, holdout_dates


def feature_baseline(train_df):
    """Per-feature decile edges on the training distribution, used later by
    churn-monitoring/drift_monitor.py to bucket a new snapshot and compute PSI
    against this baseline."""
    baseline = {}
    for col in FEATURE_COLUMNS:
        vals = train_df[col].dropna().to_numpy()
        if len(vals) < 10:
            continue
        edges = np.unique(np.quantile(vals, np.linspace(0, 1, 11)))
        baseline[col] = {
            "edges": edges.tolist(),
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
        }
    return baseline


def main():
    df = load_training_frame()
    train_df, holdout_df, train_dates, holdout_dates = time_based_split(df)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["label"]
    X_holdout, y_holdout = holdout_df[FEATURE_COLUMNS], holdout_df["label"]

    # Only ~300 independent accounts underlie these 4800 training rows (each
    # account repeats across ~16 near-identical weekly snapshots), so a
    # high-capacity model overfits fast. Kept modest-sized regardless -
    # the risk/healthy behavior ranges in generate_telemetry.py don't
    # overlap, so even a small model separates the classes almost
    # perfectly; that's a property of the synthetic data, not something
    # model capacity can or should paper over.
    model = LGBMClassifier(
        n_estimators=60,
        max_depth=3,
        num_leaves=8,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=25,
        reg_lambda=2.0,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train)

    holdout_proba = model.predict_proba(X_holdout)[:, 1]
    auc_holdout = roc_auc_score(y_holdout, holdout_proba) if y_holdout.nunique() > 1 else float("nan")

    train_proba = model.predict_proba(X_train)[:, 1]
    auc_train = roc_auc_score(y_train, train_proba) if y_train.nunique() > 1 else float("nan")

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))

    # The model is very confident on this cleanly-separable synthetic data,
    # so predict_proba clusters near 0/1 and is useless as a *display* score
    # (no gradient between accounts). Use the raw margin instead - scaled
    # once here against the training population and reused as a FIXED
    # transform at serving time, so scores stay comparable week over week
    # instead of being re-normalized against whoever happens to be in the
    # portfolio on a given scoring run.
    raw_margin_train = model.predict(X_train, raw_score=True)
    margin_lo, margin_hi = (float(x) for x in np.quantile(raw_margin_train, [0.02, 0.98]))

    # Fixed absolute score thresholds, not data quantiles: this training
    # population's score distribution is bimodal (the synthetic generator's
    # risk/healthy behavior ranges don't overlap, so most accounts land near
    # 0 or 100 with only a few genuinely borderline ones in between).
    # Quantile-based cutoffs collapse under a bimodal distribution - e.g. the
    # 55th percentile can still land inside the "0" cluster, which would
    # wipe out the Low band entirely. Fixed thresholds don't have that
    # failure mode.
    band_cutoffs = {"critical": 70.0, "high": 40.0, "medium": 15.0}

    transform_version = str(train_df["transform_version"].iloc[0])
    model_version = f"lgbm-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{transform_version}"

    import os
    os.makedirs(MODELS_DIR, exist_ok=True)

    import joblib
    joblib.dump(model, f"{MODELS_DIR}/model_{model_version}.joblib")
    joblib.dump(model, f"{MODELS_DIR}/model_latest.joblib")

    with open(f"{MODELS_DIR}/feature_baseline.json", "w") as f:
        json.dump({
            "model_version": model_version,
            "feature_columns": FEATURE_COLUMNS,
            "baseline": feature_baseline(train_df),
            "scaling": {"margin_lo": margin_lo, "margin_hi": margin_hi},
            "band_cutoffs": band_cutoffs,
        }, f, indent=2)

    report = {
        "model_version": model_version,
        "transform_version": transform_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train_rows": int(len(train_df)),
        "n_holdout_rows": int(len(holdout_df)),
        "train_dates": [d.date().isoformat() for d in train_dates],
        "holdout_dates": [d.date().isoformat() for d in holdout_dates],
        "auc_train": float(auc_train),
        "auc_holdout": float(auc_holdout),
        "feature_importance": importances,
    }
    with open(f"{MODELS_DIR}/train_report.json", "w") as f:
        json.dump(report, f, indent=2)

    with open(f"{MODELS_DIR}/current_version.json", "w") as f:
        json.dump({"model_version": model_version}, f, indent=2)

    print(f"Trained {model_version}")
    print(f"  train rows: {len(train_df)} ({len(train_dates)} snapshot dates)")
    print(f"  holdout rows: {len(holdout_df)} ({len(holdout_dates)} snapshot dates: {holdout_dates[0].date()}..{holdout_dates[-1].date()})")
    print(f"  AUC train={auc_train:.3f}  holdout={auc_holdout:.3f}")
    print(f"Wrote {MODELS_DIR}/model_{model_version}.joblib, feature_baseline.json, train_report.json")


if __name__ == "__main__":
    main()
