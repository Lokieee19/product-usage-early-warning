"""
generate_telemetry.py

Simulates RAW product telemetry for a set of B2B seat-based accounts
(modeled on something like LinkedIn Talent Solutions / Sales Navigator).

This is deliberately event-level and messy, the way real telemetry is:
one row per event, not one row per account. The feature pipeline's job
(next step) is to turn this into clean, versioned, point-in-time features.

Outputs (in ./data/):
  - accounts.csv   one row per account: contract facts
  - events.csv     one row per event: usage, support, survey, CRM, personnel

Run:
  python generate_telemetry.py
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(42)

N_ACCOUNTS = 300
SIM_START = datetime(2026, 1, 1)
SIM_END = datetime(2026, 9, 28)
SIM_DAYS = (SIM_END - SIM_START).days

# Cosmetic-only display fields - not telemetry, not model features. A real
# system would pull these from the CRM account record. Generated here just
# so the dashboard has something human-readable to show besides an account_id.
_NAME_PREFIXES = [
    "Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Hooli",
    "Vandelay", "Soylent", "Massive Dynamic", "Wonka", "Tyrell", "Cyberdyne",
    "Aperture", "Sirius", "Pinnacle", "Northwind", "Fabrikam", "Contoso",
    "Zenith", "Quantum", "Meridian", "Vertex", "Apex", "Nimbus", "Catalyst",
    "Lumen", "Beacon", "Anchor", "Summit", "Horizon", "Orbit", "Cascade",
    "Granite", "Ironclad", "Vanguard", "Pioneer", "Frontier", "Compass",
    "Sterling",
]
_NAME_SUFFIXES = ["Corporation", "Inc", "Industries", "Enterprises", "Technologies", "Group", "Holdings", "Labs"]
_INDUSTRIES = [
    "Technology", "Healthcare", "Financial Services", "Manufacturing",
    "Retail", "Media", "Software", "Consumer Goods", "Logistics", "Education",
]


def _make_company_names(n):
    """Deterministic, collision-free 'Prefix Suffix' names for n accounts."""
    combos = [(p, s) for p in _NAME_PREFIXES for s in _NAME_SUFFIXES]
    idx = RNG.choice(len(combos), size=n, replace=False)
    return [f"{combos[i][0]} {combos[i][1]}" for i in idx]


def make_accounts():
    """One row per account: contract-level facts that don't change daily."""
    company_names = _make_company_names(N_ACCOUNTS)
    rows = []
    for i in range(N_ACCOUNTS):
        account_id = f"acct_{1000 + i}"
        seats_contracted = int(RNG.choice([5, 10, 15, 25, 50, 100], p=[.25, .25, .2, .15, .1, .05]))
        contract_start = SIM_START - timedelta(days=int(RNG.integers(30, 500)))
        contract_length_days = int(RNG.choice([365, 730]))
        renewal_date = contract_start + timedelta(days=contract_length_days)
        # ensure renewal falls within a useful forward window for the demo
        while renewal_date < SIM_END:
            renewal_date += timedelta(days=contract_length_days)
        segment = RNG.choice(["smb", "midmarket", "enterprise"], p=[.5, .35, .15])

        # Latent risk flag - NOT visible to the feature pipeline directly.
        # It just biases how we generate downstream events, the way real
        # customers who are actually at risk behave differently, without
        # anyone having a labeled "risk" column in production telemetry.
        is_latent_risk = RNG.random() < 0.28

        rows.append(dict(
            account_id=account_id,
            company_name=company_names[i],
            industry=RNG.choice(_INDUSTRIES),
            segment=segment,
            seats_contracted=seats_contracted,
            contract_start=contract_start.date().isoformat(),
            renewal_date=renewal_date.date().isoformat(),
            _is_latent_risk=is_latent_risk,  # kept only for label generation later
        ))
    return pd.DataFrame(rows)


def make_events(accounts: pd.DataFrame):
    """
    One row per event. event_type is one of:
      login, search, inmail_send, inmail_reply, session_duration_min,
      support_ticket, support_csat, nps_survey, crm_sync_status,
      champion_turnover, seat_active_count
    """
    events = []

    for _, acct in accounts.iterrows():
        account_id = acct["account_id"]
        seats = acct["seats_contracted"]
        risk = acct["_is_latent_risk"]

        # Trend drift: risky accounts decay usage over the sim window,
        # healthy accounts hold steady or grow slightly. This is what
        # makes the *_trend_3m features later actually mean something.
        decay = RNG.uniform(0.55, 0.8) if risk else RNG.uniform(0.95, 1.15)
        base_active_seat_ratio = RNG.uniform(0.25, 0.55) if risk else RNG.uniform(0.6, 0.95)

        champion_turnover_day = None
        if risk and RNG.random() < 0.4:
            champion_turnover_day = int(RNG.integers(SIM_DAYS // 3, SIM_DAYS))

        for day in range(0, SIM_DAYS, 1):
            date = SIM_START + timedelta(days=day)
            progress = day / SIM_DAYS  # 0 -> 1 across the sim window
            trend_multiplier = 1 + (decay - 1) * progress

            active_seat_ratio = np.clip(
                base_active_seat_ratio * trend_multiplier + RNG.normal(0, 0.03), 0.05, 1.0
            )
            active_seats = max(1, int(round(seats * active_seat_ratio)))

            if day % 1 == 0:
                events.append((account_id, date, "seat_active_count", active_seats))

            # Usage events - scaled by active seats, noisy
            daily_login_rate = active_seats * RNG.uniform(0.5, 1.3) * trend_multiplier
            if RNG.random() < 0.9:
                events.append((account_id, date, "login", max(0, RNG.poisson(daily_login_rate))))

            if RNG.random() < 0.7:
                search_rate = active_seats * RNG.uniform(0.3, 1.0) * trend_multiplier
                events.append((account_id, date, "search", max(0, RNG.poisson(search_rate))))

            if RNG.random() < 0.5:
                inmail_rate = active_seats * RNG.uniform(0.2, 0.6) * trend_multiplier
                sends = max(0, RNG.poisson(inmail_rate))
                events.append((account_id, date, "inmail_send", sends))
                reply_rate = RNG.uniform(0.05, 0.15) if risk else RNG.uniform(0.15, 0.35)
                replies = RNG.binomial(sends, np.clip(reply_rate, 0, 1)) if sends > 0 else 0
                events.append((account_id, date, "inmail_reply", replies))

            if RNG.random() < 0.4:
                avg_session = RNG.uniform(4, 10) * trend_multiplier
                events.append((account_id, date, "session_duration_min", round(avg_session, 1)))

            # Support events - sparser, more frequent + worse for risky accounts
            ticket_prob = 0.05 if risk else 0.015
            if RNG.random() < ticket_prob:
                events.append((account_id, date, "support_ticket", 1))
                csat = RNG.uniform(1, 3) if risk else RNG.uniform(3.5, 5)
                events.append((account_id, date, "support_csat", round(csat, 1)))

            # CRM sync status - risky accounts more likely to have disabled it
            if RNG.random() < 0.01:
                sync_active = 0 if (risk and RNG.random() < 0.6) else 1
                events.append((account_id, date, "crm_sync_status", sync_active))

            # Champion turnover - single event, if it happens
            if champion_turnover_day is not None and day == champion_turnover_day:
                events.append((account_id, date, "champion_turnover", 1))

            # Quarterly-ish NPS survey
            if RNG.random() < 0.004:
                nps = RNG.integers(0, 6) if risk else RNG.integers(6, 11)
                events.append((account_id, date, "nps_survey", int(nps)))

    df = pd.DataFrame(events, columns=["account_id", "event_date", "event_type", "value"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    return df


if __name__ == "__main__":
    accounts = make_accounts()
    events = make_events(accounts)

    # Keep the latent risk flag out of the "raw telemetry" accounts file -
    # it's not something a real system would have. Save it separately so
    # step 2 (labeling for model training) can use it later without the
    # feature pipeline ever touching it.
    accounts.drop(columns=["_is_latent_risk"]).to_csv("data/accounts.csv", index=False)
    accounts[["account_id", "_is_latent_risk"]].to_csv("data/_latent_risk_labels.csv", index=False)
    events.to_csv("data/events.csv", index=False)

    print(f"Wrote {len(accounts)} accounts to data/accounts.csv")
    print(f"Wrote {len(events):,} events to data/events.csv")
    print("Wrote data/_latent_risk_labels.csv (for later model training/eval only - not a feature)")
