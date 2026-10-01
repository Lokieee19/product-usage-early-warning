"""
simulate_outcomes.py

Phase 4, step 1: outcome capture.

A real system logs this from wherever the play actually got pushed - a CRM
task, a Slack alert, a support ticket - and closes the loop when the
account eventually renews, expands, or churns. There's no real CRM/Slack
here, so this script is the honest stand-in: it logs the SAME action a real
ActionSink would (account, play, timestamp, status) via `log_action`, and
then simulates a plausible eventual outcome so the evaluation step
(evaluate.py) has something to join against. Swap `_write_action_sink` for
a real webhook/CRM-write call and the rest of the pipeline (logging shape,
evaluate.py) doesn't need to change.

Run:
  python simulate_outcomes.py
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "churn-policy"))
from policy import recommend_play  # noqa: E402

RNG = np.random.default_rng(7)

SCORES_PATH = "../churn-scoring/data/scores_latest.json"
LABELS_PATH = "../churn-pipeline/data/_latent_risk_labels.csv"
DATA_DIR = "data"


def log_action(account_id, scored_at, model_version, band, score, play_key, play_name):
    """The real ActionSink interface: this is the one function a live CRM/
    Slack integration would replace. Everything else treats its output
    (a logged row) as the source of truth, regardless of where it came from.
    """
    # Not every flagged account actually gets worked - real CS teams have
    # limited capacity, so only most (not all) Critical/High accounts get
    # the play executed. This gap is what lets evaluate.py compare outcomes
    # for played vs un-played accounts instead of every risky account
    # looking identical.
    eligible = band in ("Critical", "High")
    executed = eligible and RNG.random() < 0.7
    action_taken_at = (
        datetime.fromisoformat(scored_at) + timedelta(hours=int(RNG.integers(1, 72)))
    ).isoformat() if executed else ""
    status = "Completed" if executed and RNG.random() < 0.6 else (
        "In progress" if executed else "Pending"
    )
    return {
        "account_id": account_id,
        "scored_at": scored_at,
        "model_version": model_version,
        "band": band,
        "score": score,
        "play_key": play_key,
        "play": play_name,
        "action_taken_at": action_taken_at,
        "action_status": status,
    }


def simulate_outcome(is_latent_risk: bool, action_taken: bool):
    """Outcome probability biased by the (otherwise-hidden) ground truth and
    by whether a play was actually executed - a played Critical/High account
    is more likely to recover than one left untouched. Documented as
    synthetic: a real system reads this column from actual renewal/CRM data.
    """
    if is_latent_risk:
        churn_p = 0.62 if not action_taken else 0.30
    else:
        churn_p = 0.04 if not action_taken else 0.02
    outcome = "churned" if RNG.random() < churn_p else RNG.choice(["renewed", "expanded"], p=[0.75, 0.25])
    outcome_date = (datetime(2026, 9, 28) + timedelta(days=int(RNG.integers(14, 120)))).date().isoformat()
    return outcome, outcome_date


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(SCORES_PATH) as f:
        scores_doc = json.load(f)
    labels = pd.read_csv(LABELS_PATH).set_index("account_id")["_is_latent_risk"].to_dict()

    actions = []
    outcomes = []
    for account_id, rec in scores_doc["accounts"].items():
        top_feature = rec["top_signals"][0]["feature"] if rec["top_signals"] else None
        play = recommend_play(rec["band"], top_feature)

        action = log_action(
            account_id, scores_doc["feature_snapshot_ts"], rec["model_version"],
            rec["band"], rec["score"], play["key"], play["name"],
        )
        actions.append(action)

        action_taken = bool(action["action_taken_at"])
        outcome, outcome_date = simulate_outcome(bool(labels.get(account_id, False)), action_taken)
        outcomes.append({"account_id": account_id, "outcome": outcome, "outcome_date": outcome_date})

    actions_df = pd.DataFrame(actions)
    outcomes_df = pd.DataFrame(outcomes)
    actions_df.to_csv(f"{DATA_DIR}/actions_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    outcomes_df.to_csv(f"{DATA_DIR}/outcomes.csv", index=False)

    print(f"Wrote {len(actions_df)} rows to {DATA_DIR}/actions_log.csv")
    print(f"Wrote {len(outcomes_df)} rows to {DATA_DIR}/outcomes.csv")
    print(actions_df["action_status"].value_counts().to_string())


if __name__ == "__main__":
    main()
