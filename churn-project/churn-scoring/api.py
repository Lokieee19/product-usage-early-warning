"""
api.py

Serves the dashboard. Reads the artifacts phases 2-5 produce as files -
scores_latest.json/scores_history.json (this phase's batch-scoring cache),
../churn-policy/plays.yaml (via policy.recommend_play), ../churn-outcomes/data
(actions_log.csv, eval_report.json), ../churn-monitoring/data/drift_report.json
- rather than importing across those phases' own logic, so each phase stays
an independently-runnable script and the API is a thin read + on-demand
scoring layer on top.

Every response is shaped to match churn-dashboard/src/data/mockData.js
exactly, so the frontend swaps a static import for a fetch and nothing
downstream (StatCard, AccountsTable, AccountDetailPanel, ...) needs to change.

Run:
  uvicorn api:app --reload --port 8000
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.join(_THIS_DIR, "..", "churn-policy"))
sys.path.insert(0, os.path.join(_THIS_DIR, "..", "churn-pipeline"))

import score as scoring  # noqa: E402
from policy import ACTION_DESCRIPTIONS, load_plays, recommend_play  # noqa: E402
from feature_labels import friendly_label  # noqa: E402
import feature_pipeline  # noqa: E402

ACCOUNTS_PATH = "../churn-pipeline/data/accounts.csv"
EVENTS_PATH = "../churn-pipeline/data/events.csv"
FEATURES_PATH = "../churn-pipeline/data/features.csv"
SCORES_LATEST_PATH = "data/scores_latest.json"
SCORES_HISTORY_PATH = "data/scores_history.json"
ACTIONS_LOG_PATH = "../churn-outcomes/data/actions_log.csv"
EVAL_REPORT_PATH = "../churn-outcomes/data/eval_report.json"
DRIFT_REPORT_PATH = "../churn-monitoring/data/drift_report.json"

BAND_COLORS = {"Critical": "#E24B4A", "High": "#F2A623", "Medium": "#EFC245", "Low": "#3FC98A"}
BAND_TONE = {"Critical": "danger", "High": "warning", "Medium": "accent", "Low": "success"}
BAND_URGENCY = {
    "Critical": "Immediate action recommended",
    "High": "Action recommended this week",
    "Medium": "Monitor closely, no urgent action yet",
    "Low": "No action needed",
}

SEAT_PRICE_PER_YEAR = 600
SEGMENT_ARR_MULTIPLIER = {"smb": 1.0, "midmarket": 1.3, "enterprise": 1.8}

app = FastAPI(title="Churn early-warning API")

# Local demo only - a real deployment would restrict this to the dashboard's
# actual origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loaded once at startup - contract facts and raw events don't change
# without re-running the Phase 1 pipeline (which requires a restart anyway
# since the model/score caches would also need refreshing).
_accounts_df = pd.read_csv(ACCOUNTS_PATH)
_events_df = pd.read_csv(EVENTS_PATH)
_events_df["event_date"] = pd.to_datetime(_events_df["event_date"])

_model, _model_version, _baseline, _scaling, _band_cutoffs = scoring.load_model()


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _scores_latest():
    doc = _read_json(SCORES_LATEST_PATH)
    if doc is None:
        raise HTTPException(503, "No scores yet - run churn-scoring/score.py first.")
    return doc


def _account_row(account_id):
    row = _accounts_df[_accounts_df["account_id"] == account_id]
    if row.empty:
        raise HTTPException(404, f"Unknown account_id {account_id}")
    return row.iloc[0]


def _initials(company_name):
    parts = [p for p in company_name.split(" ") if p]
    return "".join(p[0] for p in parts[:2]).upper()


def _arr(row):
    multiplier = SEGMENT_ARR_MULTIPLIER.get(row["segment"], 1.0)
    return int(row["seats_contracted"]) * SEAT_PRICE_PER_YEAR * multiplier


def _format_arr(value):
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value / 1000:.0f}K"


def _format_money_m(value):
    return f"${value / 1_000_000:.1f}M"


PLAN_LABELS = {"smb": "SMB", "midmarket": "Midmarket", "enterprise": "Enterprise"}


def _plan(row):
    return PLAN_LABELS.get(row["segment"], row["segment"])


def _renewal_display(row):
    return pd.Timestamp(row["renewal_date"]).strftime("%b %-d, %Y") if os.name != "nt" \
        else pd.Timestamp(row["renewal_date"]).strftime("%b %d, %Y").replace(" 0", " ")


@app.get("/api/summary")
def get_summary():
    scores_doc = _scores_latest()
    accounts = scores_doc["accounts"]

    critical = [a for a in accounts.values() if a["band"] == "Critical"]
    high = [a for a in accounts.values() if a["band"] == "High"]
    at_risk_90 = [a for a in accounts.values() if a["days_to_renewal"] is not None and a["days_to_renewal"] <= 90]

    revenue_at_risk = 0
    for a in critical + high:
        row = _accounts_df[_accounts_df["account_id"] == a["account_id"]]
        if not row.empty:
            revenue_at_risk += _arr(row.iloc[0])

    drift_report = _read_json(DRIFT_REPORT_PATH, {})
    n_drift_alerts = drift_report.get("n_features_alerting", 0)

    return [
        {
            "key": "total", "label": "Total accounts", "value": f"{len(_accounts_df):,}",
            "delta": "0%", "trend": "flat", "icon": "users",
        },
        {
            "key": "highRisk", "label": "High risk accounts", "value": str(len(critical)),
            "delta": f"{len(critical) / max(len(accounts), 1) * 100:.0f}% of portfolio",
            "trend": "flat", "tone": "danger", "icon": "alertTriangle",
        },
        {
            "key": "atRisk90", "label": "At risk (renewal ≤ 90 days)", "value": str(len(at_risk_90)),
            "delta": f"{len(at_risk_90) / max(len(accounts), 1) * 100:.0f}% of portfolio",
            "trend": "flat", "tone": "accent", "icon": "shield",
        },
        {
            "key": "revenue", "label": "Revenue at risk", "value": _format_money_m(revenue_at_risk),
            "delta": "Critical + High bands", "trend": "flat", "tone": "success", "icon": "dollar",
        },
        {
            "key": "drift", "label": "Feature drift alerts", "value": str(n_drift_alerts),
            "delta": "Requires attention" if n_drift_alerts else "Stable", "trend": "flat",
            "tone": "warning", "icon": "activity",
        },
    ]


@app.get("/api/risk-distribution")
def get_risk_distribution():
    scores_doc = _scores_latest()
    accounts = list(scores_doc["accounts"].values())
    total = len(accounts)
    counts = pd.Series([a["band"] for a in accounts]).value_counts()
    order = ["Critical", "High", "Medium", "Low"]
    return [
        {
            "band": band,
            "count": int(counts.get(band, 0)),
            "pct": round(counts.get(band, 0) / total * 100, 1) if total else 0.0,
            "color": BAND_COLORS[band],
        }
        for band in order
    ]


@app.get("/api/risk-trend")
def get_risk_trend():
    history_doc = _read_json(SCORES_HISTORY_PATH, {"history": []})
    out = []
    for point in history_doc["history"]:
        d = datetime.fromisoformat(point["date"])
        out.append({"date": d.strftime("%b %d"), "value": point["value"]})
    return out


def _account_summary(account_id, rec, accounts_row, as_of):
    top_signal = rec["top_signals"][0]["label"] if rec["top_signals"] else "No significant signal"
    return {
        "id": account_id,
        "initials": _initials(accounts_row["company_name"]),
        "name": accounts_row["company_name"],
        "industry": accounts_row["industry"],
        "plan": _plan(accounts_row),
        "arr": _arr(accounts_row),
        "score": rec["score"],
        "band": rec["band"],
        "wow": rec["wow"],
        "usage": _usage_trend(account_id, as_of, 30),
        "signal": top_signal,
        "renewalDays": rec["days_to_renewal"],
        "renewal": _renewal_display(accounts_row),
    }


@app.get("/api/accounts")
def get_accounts():
    scores_doc = _scores_latest()
    as_of = pd.Timestamp(scores_doc["feature_snapshot_ts"])
    out = []
    for account_id, rec in scores_doc["accounts"].items():
        row = _accounts_df[_accounts_df["account_id"] == account_id]
        if row.empty:
            continue
        out.append(_account_summary(account_id, rec, row.iloc[0], as_of))
    out.sort(key=lambda a: a["score"], reverse=True)
    return out


def _usage_trend(account_id, as_of, window_days):
    end = as_of
    start = end - pd.Timedelta(days=window_days)
    prev_start = start - pd.Timedelta(days=window_days)
    sub = _events_df[(_events_df["account_id"] == account_id) & (_events_df["event_type"] == "login")]
    recent = sub[(sub["event_date"] > start) & (sub["event_date"] <= end)]["value"].sum()
    baseline = sub[(sub["event_date"] > prev_start) & (sub["event_date"] <= start)]["value"].sum()
    denom = abs(baseline) + 1.0
    pct = np.clip((recent - baseline) / denom, -1, 1) * 100
    return round(pct)


def _usage90d_series(account_id, as_of):
    sub = _events_df[
        (_events_df["account_id"] == account_id)
        & (_events_df["event_type"] == "login")
        & (_events_df["event_date"] > as_of - pd.Timedelta(days=90))
        & (_events_df["event_date"] <= as_of)
    ]
    if sub.empty:
        return []
    daily = sub.groupby("event_date")["value"].sum()
    daily = daily.reindex(pd.date_range(as_of - pd.Timedelta(days=89), as_of, freq="D"), fill_value=0)
    bins = np.array_split(daily.values, 6)
    bin_dates = np.array_split(daily.index, 6)
    return [
        {"date": bin_dates[i][-1].strftime("%b %-d") if os.name != "nt" else bin_dates[i][-1].strftime("%b %d").lstrip("0"),
         "value": float(np.mean(b)) if len(b) else 0.0}
        for i, b in enumerate(bins)
    ]


@app.get("/api/accounts/{account_id}")
def get_account_detail(account_id: str):
    scores_doc = _scores_latest()
    rec = scores_doc["accounts"].get(account_id)
    if rec is None:
        raise HTTPException(404, f"No score for account_id {account_id}")
    row = _account_row(account_id)
    as_of = pd.Timestamp(scores_doc["feature_snapshot_ts"])

    top_feature = rec["top_signals"][0]["feature"] if rec["top_signals"] else None
    play = recommend_play(rec["band"], top_feature)

    return {
        "name": row["company_name"],
        "industry": row["industry"],
        "plan": _plan(row),
        "arr": _format_arr(_arr(row)),
        "renewalDays": rec["days_to_renewal"],
        "renewal": _renewal_display(row),
        "score": rec["score"],
        "band": rec["band"],
        "wow": rec["wow"],
        "urgency": BAND_URGENCY[rec["band"]],
        "signals": [{"label": s["label"], "pct": s["pct"]} for s in rec["top_signals"]],
        "play": {"key": play["key"], "name": play["name"], "steps": play["steps"]},
        "usage90d": _usage90d_series(account_id, as_of),
        "last30": f"{_usage_trend(account_id, as_of, 30):+d}%",
        "last7": f"{_usage_trend(account_id, as_of, 7):+d}%",
        "attribution": [
            {"signal": a["signal"], "contribution": a["contribution"], "comparison": a["comparison"]}
            for a in rec["attribution"]
        ],
        "totalScore": rec["score"],
    }


@app.get("/api/accounts/{account_id}/rescore")
def rescore_account(account_id: str):
    """On-demand scoring path: recompute features live from raw events as of
    today, rather than reading the pre-scored cache - the "ad hoc" case
    (vs the batch-precomputed default every other endpoint reads)."""
    row = _account_row(account_id)
    accounts_one = pd.DataFrame([row])
    events = _events_df[_events_df["account_id"] == account_id]
    as_of = datetime.now()

    feat = feature_pipeline.compute_features(events, accounts_one, as_of)
    rec = scoring.score_snapshot(_model, _model_version, _baseline, _scaling, _band_cutoffs, feat, as_of.date().isoformat())
    return rec[account_id]


@app.get("/api/recent-actions")
def get_recent_actions(limit: int = 8):
    if not os.path.exists(ACTIONS_LOG_PATH):
        return []
    df = pd.read_csv(ACTIONS_LOG_PATH)
    df["sort_ts"] = df["action_taken_at"].fillna(df["scored_at"])
    df = df.sort_values("sort_ts", ascending=False).head(limit)

    out = []
    for _, r in df.iterrows():
        acc_row = _accounts_df[_accounts_df["account_id"] == r["account_id"]]
        name = acc_row.iloc[0]["company_name"] if not acc_row.empty else r["account_id"]
        action_desc = ACTION_DESCRIPTIONS.get(r.get("play_key", "default"), ACTION_DESCRIPTIONS["default"])
        date_val = r["action_taken_at"] if isinstance(r["action_taken_at"], str) and r["action_taken_at"] else r["scored_at"]
        out.append({
            "accountId": r["account_id"],
            "account": name,
            "play": r["play"],
            "action": action_desc,
            "status": r["action_status"],
            "date": date_val,
        })
    return out


PLAY_ICONS = {
    "usage_decay": "zap", "low_seat_utilization": "users", "feature_abandonment": "layers",
    "support_friction": "life-buoy", "champion_turnover": "user-round", "crm_sync_disabled": "refresh-cw",
    "low_nps": "message-circle", "renewal_urgency": "calendar-clock", "default": "activity",
}
PLAY_COLORS = ["violet", "blue", "orange", "green", "pink", "indigo"]


@app.get("/api/plays")
def get_plays():
    """The real score -> play policy from churn-policy/plays.yaml, so the
    Playbooks page shows the same interventions the scoring/policy layer
    actually recommends on the account-detail endpoint - not a fixed,
    hand-written list."""
    doc = load_plays()
    plays = doc["plays"]
    signal_to_play = doc["signal_to_play"]

    triggers = {}
    for feature, key in signal_to_play.items():
        triggers.setdefault(key, []).append(friendly_label(feature))

    out = []
    for i, (key, play) in enumerate(plays.items()):
        if key == "default":
            continue
        out.append({
            "id": key,
            "title": play["name"],
            "category": triggers.get(key, ["General signal"])[0],
            "steps": list(play["steps"]),
            "color": PLAY_COLORS[i % len(PLAY_COLORS)],
            "icon": PLAY_ICONS.get(key, "activity"),
            "band": "High risk" if key in ("support_friction", "renewal_urgency", "usage_decay") else "Medium-high risk",
            "trigger": " / ".join(triggers.get(key, [])) or "Default monitoring signal",
        })
    return out


@app.get("/api/drift")
def get_drift():
    """The real feature_psi report from churn-monitoring/drift_monitor.py,
    with human-readable feature labels attached for the Monitoring page's
    Input Drift tab."""
    report = _read_json(DRIFT_REPORT_PATH)
    if report is None:
        raise HTTPException(503, "No drift report yet - run churn-monitoring/drift_monitor.py first.")
    signals = [
        {"feature": feature, "name": friendly_label(feature), "psi": round(v["psi"], 4), "alert": v["alert"]}
        for feature, v in report["feature_psi"].items()
    ]
    signals.sort(key=lambda s: s["psi"], reverse=True)
    return {
        "asOfDate": report["as_of_date"],
        "alertThreshold": report["alert_threshold"],
        "nFeaturesAlerting": report["n_features_alerting"],
        "signals": signals,
    }


@app.get("/api/meta")
def get_meta():
    """Live snapshot metadata for the footer/header - the data this
    dashboard is showing is real (not a fixture), so show what it's as-of."""
    scores_doc = _scores_latest()
    return {
        "modelVersion": scores_doc["model_version"],
        "asOf": scores_doc["feature_snapshot_ts"],
    }


@app.get("/api/model-performance")
def get_model_performance():
    eval_report = _read_json(EVAL_REPORT_PATH)
    if eval_report is None:
        raise HTTPException(503, "No eval report yet - run churn-outcomes/evaluate.py first.")

    auc = eval_report["risk_ranking_quality_auc"]
    coverage = eval_report["attribution_coverage"]
    p95 = eval_report["p95_latency_ms"]
    drift_acc = eval_report["drift_alert_accuracy"]

    return {
        "metrics": [
            {"label": "Risk ranking quality", "value": f"{auc:.2f}", "delta": "gate ≥ 0.75"},
            {"label": "Attribution coverage", "value": f"{coverage * 100:.1f}%", "delta": "target 100%"},
            {"label": "p95 latency", "value": f"{p95:.0f} ms", "delta": "cache-served"},
            {"label": "Drift alert accuracy", "value": f"{drift_acc * 100:.1f}%" if drift_acc is not None else "n/a", "delta": "gate ≥ 60%"},
        ],
        "gate": eval_report["gate"],
        "gateChecks": eval_report.get("gate_checks", {}),
        "p95LatencyMs": p95,
        "attributionCoverage": coverage,
        "playEffectiveness": eval_report.get("play_effectiveness"),
    }
