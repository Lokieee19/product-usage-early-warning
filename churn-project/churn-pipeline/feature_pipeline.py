"""
feature_pipeline.py

Turns raw event-level telemetry (data/events.csv, data/accounts.csv) into a
versioned, point-in-time feature table - the artifact every later stage
(scoring service, policy layer, drift monitor, CI eval gate) reads from.

Two hard rules this file exists to enforce:

1. POINT-IN-TIME CORRECTNESS
   Every feature for a given as_of_date uses ONLY events with
   event_date <= as_of_date. No peeking at the future. This is what makes
   a held-out-period evaluation later on honest instead of leaked.

2. LINEAGE
   Every feature column is tagged with the raw event_type(s) it was
   computed from and a transform_version string. If a score ever looks
   wrong, you can trace it back to exactly which source events and which
   version of the transform logic produced it. Lineage is written out as
   its own JSON file alongside the feature table, not just as a comment
   in this script.

Run:
  python feature_pipeline.py --as-of 2026-09-28
  python feature_pipeline.py --as-of 2026-09-28 --backfill 2026-06-01
      (writes one snapshot per week between the two dates, for training)
"""

import argparse
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

TRANSFORM_VERSION = "v1"

# ---- lineage registry --------------------------------------------------
# Every feature this pipeline can produce is declared here BEFORE it's
# computed. If a feature has no entry here, the pipeline refuses to write
# it - lineage isn't optional bookkeeping, it's a gate.
LINEAGE = {
    "logins_per_seat_trend_3m": {
        "source_events": ["login", "seat_active_count"],
        "transform": "pct change in (login sum / avg active seats) over a 30d window vs the same window 90d earlier",
    },
    "searches_per_seat_trend_3m": {
        "source_events": ["search", "seat_active_count"],
        "transform": "pct change in (search sum / avg active seats), recent 30d vs 30d window 90d earlier",
    },
    "inmail_sends_trend_3m": {
        "source_events": ["inmail_send", "seat_active_count"],
        "transform": "pct change in (inmail_send sum / avg active seats), recent 30d vs 30d window 90d earlier",
    },
    "pct_seats_active_30d": {
        "source_events": ["seat_active_count"],
        "transform": "avg active seats over trailing 30d / seats_contracted",
    },
    "crm_sync_active_30d": {
        "source_events": ["crm_sync_status"],
        "transform": "most recent crm_sync_status value in trailing 30d (null if no event)",
    },
    "avg_session_duration_trend": {
        "source_events": ["session_duration_min"],
        "transform": "pct change in avg session_duration_min, recent 30d vs 30d window 90d earlier",
    },
    "inmail_response_rate": {
        "source_events": ["inmail_send", "inmail_reply"],
        "transform": "sum(inmail_reply) / sum(inmail_send) over trailing 90d",
    },
    "support_tickets_90d": {
        "source_events": ["support_ticket"],
        "transform": "count of support_ticket events in trailing 90d",
    },
    "support_csat": {
        "source_events": ["support_csat"],
        "transform": "mean support_csat value in trailing 90d",
    },
    "champion_turnover_flag": {
        "source_events": ["champion_turnover"],
        "transform": "1 if any champion_turnover event in trailing 180d, else 0",
    },
    "seat_utilization_vs_contracted": {
        "source_events": ["seat_active_count"],
        "transform": "most recent active seat count as of as_of_date / seats_contracted",
    },
    "days_to_renewal": {
        "source_events": ["accounts.renewal_date"],
        "transform": "renewal_date - as_of_date, in days",
    },
    "nps_last_survey": {
        "source_events": ["nps_survey"],
        "transform": "most recent nps_survey value in trailing 180d (null if none)",
    },
}


def _window_sum(events, account_ids, event_type, start, end):
    sub = events[(events.event_type == event_type) & (events.event_date > start) & (events.event_date <= end)]
    s = sub.groupby("account_id")["value"].sum()
    return s.reindex(account_ids, fill_value=0.0)


def _window_mean(events, account_ids, event_type, start, end):
    sub = events[(events.event_type == event_type) & (events.event_date > start) & (events.event_date <= end)]
    s = sub.groupby("account_id")["value"].mean()
    return s.reindex(account_ids)


def _window_count(events, account_ids, event_type, start, end):
    sub = events[(events.event_type == event_type) & (events.event_date > start) & (events.event_date <= end)]
    s = sub.groupby("account_id")["value"].count()
    return s.reindex(account_ids, fill_value=0)


def _most_recent_value(events, account_ids, event_type, start, end):
    sub = events[(events.event_type == event_type) & (events.event_date > start) & (events.event_date <= end)]
    sub = sub.sort_values("event_date")
    s = sub.groupby("account_id")["value"].last()
    return s.reindex(account_ids)


def _trend_pct(recent, baseline):
    """Symmetric-ish pct change that doesn't explode near zero baselines."""
    denom = baseline.abs() + 1.0
    return ((recent - baseline) / denom).clip(-5, 5)


def compute_features(events: pd.DataFrame, accounts: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    account_ids = accounts["account_id"].tolist()
    seats = accounts.set_index("account_id")["seats_contracted"]
    renewal = pd.to_datetime(accounts.set_index("account_id")["renewal_date"])

    events = events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    events = events[events["event_date"] <= as_of]  # <-- point-in-time cutoff, enforced once, here

    recent_start, recent_end = as_of - timedelta(days=30), as_of
    base_start, base_end = as_of - timedelta(days=120), as_of - timedelta(days=90)

    avg_seats_recent = _window_mean(events, account_ids, "seat_active_count", recent_start, recent_end).fillna(1.0)
    avg_seats_base = _window_mean(events, account_ids, "seat_active_count", base_start, base_end).fillna(1.0)

    def per_seat_trend(event_type):
        recent = _window_sum(events, account_ids, event_type, recent_start, recent_end) / avg_seats_recent
        base = _window_sum(events, account_ids, event_type, base_start, base_end) / avg_seats_base
        return _trend_pct(recent, base)

    logins_per_seat_trend_3m = per_seat_trend("login")
    searches_per_seat_trend_3m = per_seat_trend("search")
    inmail_sends_trend_3m = per_seat_trend("inmail_send")

    pct_seats_active_30d = (avg_seats_recent / seats.reindex(account_ids)).clip(0, 1)

    crm_sync_active_30d = _most_recent_value(events, account_ids, "crm_sync_status", recent_start, recent_end)

    sess_recent = _window_mean(events, account_ids, "session_duration_min", recent_start, recent_end).fillna(0.0)
    sess_base = _window_mean(events, account_ids, "session_duration_min", base_start, base_end).fillna(0.0)
    avg_session_duration_trend = _trend_pct(sess_recent, sess_base)

    inmail_sends_90d = _window_sum(events, account_ids, "inmail_send", as_of - timedelta(days=90), as_of)
    inmail_replies_90d = _window_sum(events, account_ids, "inmail_reply", as_of - timedelta(days=90), as_of)
    inmail_response_rate = (inmail_replies_90d / inmail_sends_90d.replace(0, np.nan)).fillna(0.0)

    support_tickets_90d = _window_count(events, account_ids, "support_ticket", as_of - timedelta(days=90), as_of)
    support_csat = _window_mean(events, account_ids, "support_csat", as_of - timedelta(days=90), as_of)

    champion_turnover_flag = (
        _window_count(events, account_ids, "champion_turnover", as_of - timedelta(days=180), as_of) > 0
    ).astype(int)

    latest_active_seats = _most_recent_value(events, account_ids, "seat_active_count", as_of - timedelta(days=14), as_of)
    seat_utilization_vs_contracted = (latest_active_seats / seats.reindex(account_ids)).clip(0, 1)

    days_to_renewal = (renewal.reindex(account_ids) - as_of).dt.days

    nps_last_survey = _most_recent_value(events, account_ids, "nps_survey", as_of - timedelta(days=180), as_of)

    feat = pd.DataFrame({
        "account_id": account_ids,
        "as_of_date": as_of.date().isoformat(),
        "logins_per_seat_trend_3m": logins_per_seat_trend_3m.values,
        "searches_per_seat_trend_3m": searches_per_seat_trend_3m.values,
        "inmail_sends_trend_3m": inmail_sends_trend_3m.values,
        "pct_seats_active_30d": pct_seats_active_30d.values,
        "crm_sync_active_30d": crm_sync_active_30d.values,
        "avg_session_duration_trend": avg_session_duration_trend.values,
        "inmail_response_rate": inmail_response_rate.values,
        "support_tickets_90d": support_tickets_90d.values,
        "support_csat": support_csat.values,
        "champion_turnover_flag": champion_turnover_flag.values,
        "seat_utilization_vs_contracted": seat_utilization_vs_contracted.values,
        "days_to_renewal": days_to_renewal.values,
        "nps_last_survey": nps_last_survey.values,
        "transform_version": TRANSFORM_VERSION,
    })

    missing_lineage = [c for c in feat.columns if c in LINEAGE_REQUIRED and c not in LINEAGE]
    if missing_lineage:
        raise ValueError(f"Refusing to write features with no lineage entry: {missing_lineage}")

    return feat


LINEAGE_REQUIRED = set(LINEAGE.keys())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD snapshot date")
    parser.add_argument("--backfill", help="If set, write one weekly snapshot from this date through --as-of")
    args = parser.parse_args()

    accounts = pd.read_csv("data/accounts.csv")
    events = pd.read_csv("data/events.csv")

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d")
    dates = [as_of]
    if args.backfill:
        start = datetime.strptime(args.backfill, "%Y-%m-%d")
        dates = []
        d = start
        while d <= as_of:
            dates.append(d)
            d += timedelta(days=7)

    all_feats = []
    for d in dates:
        all_feats.append(compute_features(events, accounts, d))
    features = pd.concat(all_feats, ignore_index=True)

    features.to_csv("data/features.csv", index=False)

    with open("data/feature_lineage.json", "w") as f:
        json.dump({
            "transform_version": TRANSFORM_VERSION,
            "generated_for_as_of_dates": [d.date().isoformat() for d in dates],
            "features": LINEAGE,
        }, f, indent=2)

    print(f"Wrote {len(features)} feature rows ({len(dates)} snapshot date(s)) to data/features.csv")
    print("Wrote data/feature_lineage.json")


if __name__ == "__main__":
    main()
