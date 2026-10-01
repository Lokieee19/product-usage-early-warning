"""
feature_labels.py

Maps the 13 lineage-tagged features from churn-pipeline/feature_pipeline.py
to human-readable "signal" names for the UI, plus how to format each
feature's raw value for the account-detail attribution table.

Shared by churn-scoring/score.py (top_contributing_features), churn-policy
(picking a play from the top signal), and churn-outcomes/evaluate.py
(attribution coverage = % of accounts whose top signal has an entry here).
"""

FEATURE_LABELS = {
    "logins_per_seat_trend_3m": "Usage decay",
    "searches_per_seat_trend_3m": "Search activity decline",
    "inmail_sends_trend_3m": "Outreach activity decline",
    "pct_seats_active_30d": "Low seat utilization",
    "crm_sync_active_30d": "CRM sync disabled",
    "avg_session_duration_trend": "Session duration decline",
    "inmail_response_rate": "Low response rate",
    "support_tickets_90d": "Support friction",
    "support_csat": "Low support satisfaction",
    "champion_turnover_flag": "Champion turnover",
    "seat_utilization_vs_contracted": "Seat utilization below contract",
    "days_to_renewal": "Renewal approaching",
    "nps_last_survey": "Low NPS score",
}

# Features that are percentages/ratios in [0, 1] or trend fractions - render as "%".
_PCT_FEATURES = {
    "logins_per_seat_trend_3m", "searches_per_seat_trend_3m", "inmail_sends_trend_3m",
    "pct_seats_active_30d", "avg_session_duration_trend", "inmail_response_rate",
    "seat_utilization_vs_contracted",
}


def friendly_label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature)


def format_value(feature: str, value) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v != v:  # NaN
        return "n/a"
    if feature in _PCT_FEATURES:
        return f"{v * 100:.0f}%"
    if feature == "support_csat" or feature == "nps_last_survey":
        return f"{v:.1f}"
    if feature == "days_to_renewal":
        return f"{v:.0f}d"
    return f"{v:.2f}"
