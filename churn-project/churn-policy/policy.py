"""
policy.py

Phase 3: score -> play mapping, kept as a versioned config (plays.yaml)
separate from the model artifact, so plays can be retuned without
retraining. Used by churn-scoring/api.py (account-detail response) and
churn-outcomes/simulate_outcomes.py (deciding what action gets "taken").
"""

import os

import yaml

_PLAYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plays.yaml")

BANDS_ELIGIBLE_FOR_A_PLAY = {"Critical", "High"}

# Short, past-tense description of "what got logged" for a play key - used
# by the Recent Actions feed. Distinct from the play's own multi-step plan.
ACTION_DESCRIPTIONS = {
    "usage_decay": "Contacted customer",
    "low_seat_utilization": "Sent seat utilization report",
    "feature_abandonment": "Sent feature walkthrough",
    "support_friction": "Created support escalation",
    "champion_turnover": "Scheduled intro call",
    "crm_sync_disabled": "Notified account admin",
    "low_nps": "Followed up on NPS response",
    "renewal_urgency": "Escalated to account executive",
    "default": "Logged for monitoring",
}


def load_plays():
    with open(_PLAYS_PATH) as f:
        return yaml.safe_load(f)


_PLAYS_CACHE = None


def _plays():
    global _PLAYS_CACHE
    if _PLAYS_CACHE is None:
        _PLAYS_CACHE = load_plays()
    return _PLAYS_CACHE


def recommend_play(band: str, top_signal_feature: str | None):
    """Returns {"key": ..., "name": ..., "steps": [...]} for this account.

    `top_signal_feature` is the raw feature name (e.g. "logins_per_seat_trend_3m")
    of the account's #1 SHAP-contributing feature, from churn-scoring/score.py.
    """
    doc = _plays()
    plays = doc["plays"]
    signal_to_play = doc["signal_to_play"]

    if band not in BANDS_ELIGIBLE_FOR_A_PLAY:
        key = "default"
    else:
        key = signal_to_play.get(top_signal_feature, "default")

    play = plays.get(key, plays["default"])
    return {"key": key, "name": play["name"], "steps": list(play["steps"])}
