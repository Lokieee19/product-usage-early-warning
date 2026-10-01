"""
score.py

Phase 2, step 2: batch-score the account portfolio with the current model
artifact and write the result to a cache the API reads from (data/scores_latest.json)
instead of scoring on every request - the "pre-score nightly, serve from cache"
pattern. Also rescoes every historical snapshot in features.csv to build
data/scores_history.json for the risk-trend chart, and separately exposes
score_snapshot() so api.py can do a live on-demand rescore for one account.

Run:
  python score.py
"""

import json
import os

import numpy as np
import pandas as pd
import joblib

from feature_labels import friendly_label, format_value

FEATURES_PATH = "../churn-pipeline/data/features.csv"
MODELS_DIR = "models"
DATA_DIR = "data"

FEATURE_COLUMNS = [
    "logins_per_seat_trend_3m", "searches_per_seat_trend_3m", "inmail_sends_trend_3m",
    "pct_seats_active_30d", "crm_sync_active_30d", "avg_session_duration_trend",
    "inmail_response_rate", "support_tickets_90d", "support_csat",
    "champion_turnover_flag", "seat_utilization_vs_contracted", "days_to_renewal",
    "nps_last_survey",
]

def load_model():
    model = joblib.load(f"{MODELS_DIR}/model_latest.joblib")
    with open(f"{MODELS_DIR}/feature_baseline.json") as f:
        baseline_doc = json.load(f)
    return model, baseline_doc["model_version"], baseline_doc["baseline"], baseline_doc["scaling"], baseline_doc["band_cutoffs"]


def _prepare_X(df):
    X = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    return X


def score_frame(model, df, scaling):
    """Returns (scores 0-100 array, shap_values matrix aligned to FEATURE_COLUMNS, X).

    Score is the model's raw margin, rescaled 0-100 against the FIXED
    training-time range in `scaling` (see train_model.py) rather than
    predict_proba, which saturates near 0/1 on this cleanly-separable data
    and would give every account a near-identical score.
    """
    # Cached dashboard reads do not need SHAP's expensive dependency imports.
    import shap

    X = _prepare_X(df)
    raw_margin = model.predict(X, raw_score=True)
    scores = np.clip(
        100 * (raw_margin - scaling["margin_lo"]) / (scaling["margin_hi"] - scaling["margin_lo"]), 0, 100
    )
    scores = np.round(scores).astype(int)

    explainer = shap.TreeExplainer(model)
    raw_shap = explainer.shap_values(X)
    if isinstance(raw_shap, list):
        shap_values = raw_shap[1] if len(raw_shap) > 1 else raw_shap[0]
    else:
        shap_values = raw_shap
    return scores, shap_values, X


def assign_bands(scores, band_cutoffs):
    bands = []
    for s in scores:
        if s >= band_cutoffs["critical"]:
            bands.append("Critical")
        elif s >= band_cutoffs["high"]:
            bands.append("High")
        elif s >= band_cutoffs["medium"]:
            bands.append("Medium")
        else:
            bands.append("Low")
    return bands


def top_signals_and_attribution(X_row, shap_row, baseline):
    abs_shap = np.abs(shap_row)
    order = np.argsort(-abs_shap)
    top4 = order[:4]
    sum_top4 = abs_shap[top4].sum() or 1e-9
    sum_all = abs_shap.sum() or 1e-9

    signals = []
    attribution = []
    for idx in top4:
        feat = FEATURE_COLUMNS[idx]
        current_value = X_row[feat]
        baseline_mean = baseline.get(feat, {}).get("mean")
        signals.append({
            "label": friendly_label(feat),
            "feature": feat,
            "pct": int(round(100 * abs_shap[idx] / sum_top4)),
        })
        attribution.append({
            "signal": friendly_label(feat),
            "feature": feat,
            "contribution": int(round(100 * abs_shap[idx] / sum_all)),
            "comparison": f"{format_value(feat, current_value)} vs {format_value(feat, baseline_mean)}",
        })
    return signals, attribution


def score_snapshot(model, model_version, baseline, scaling, band_cutoffs, df, as_of_date):
    """Score one snapshot's worth of rows (one row per account). Returns a
    dict keyed by account_id with score/band/signals/attribution - the shape
    cached in data/scores_latest.json, and reusable for on-demand rescoring."""
    scores, shap_values, X = score_frame(model, df, scaling)
    bands = assign_bands(scores, band_cutoffs)

    out = {}
    for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
        account_id = row["account_id"]
        signals, attribution = top_signals_and_attribution(X.iloc[i], shap_values[i], baseline)
        out[account_id] = {
            "account_id": account_id,
            "score": int(scores[i]),
            "band": bands[i],
            "model_version": model_version,
            "feature_snapshot_ts": as_of_date,
            "top_signals": signals,
            "attribution": attribution,
            "days_to_renewal": None if pd.isna(row["days_to_renewal"]) else int(row["days_to_renewal"]),
        }
    return out


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    model, model_version, baseline, scaling, band_cutoffs = load_model()

    feat = pd.read_csv(FEATURES_PATH)
    feat["as_of_date"] = feat["as_of_date"].astype(str)
    dates = sorted(feat["as_of_date"].unique())
    latest_date = dates[-1]
    prev_date = dates[-2] if len(dates) > 1 else None

    latest_df = feat[feat["as_of_date"] == latest_date]
    latest_scores = score_snapshot(model, model_version, baseline, scaling, band_cutoffs, latest_df, latest_date)

    if prev_date:
        prev_df = feat[feat["as_of_date"] == prev_date]
        prev_scores_only, _, _ = score_frame(model, prev_df, scaling)
        prev_by_account = dict(zip(prev_df["account_id"], prev_scores_only.astype(int)))
    else:
        prev_by_account = {}

    for account_id, rec in latest_scores.items():
        rec["wow"] = rec["score"] - int(prev_by_account.get(account_id, rec["score"]))

    with open(f"{DATA_DIR}/scores_latest.json", "w") as f:
        json.dump({
            "model_version": model_version,
            "feature_snapshot_ts": latest_date,
            "accounts": latest_scores,
        }, f, indent=2)

    # History across every backfilled snapshot, for the risk-trend chart:
    # count of accounts in Critical/High band at each as_of_date.
    history = []
    for d in dates:
        d_df = feat[feat["as_of_date"] == d]
        d_scores, _, _ = score_frame(model, d_df, scaling)
        d_bands = assign_bands(d_scores, band_cutoffs)
        at_risk = sum(1 for b in d_bands if b in ("Critical", "High"))
        history.append({"date": d, "value": at_risk})

    with open(f"{DATA_DIR}/scores_history.json", "w") as f:
        json.dump({"model_version": model_version, "history": history}, f, indent=2)

    band_counts = pd.Series([r["band"] for r in latest_scores.values()]).value_counts()
    print(f"Scored {len(latest_scores)} accounts as of {latest_date} with {model_version}")
    print(band_counts.to_string())
    print(f"Wrote {DATA_DIR}/scores_latest.json and {DATA_DIR}/scores_history.json")


if __name__ == "__main__":
    main()
