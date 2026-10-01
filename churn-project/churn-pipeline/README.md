# Step 1 - Telemetry & feature pipeline

This is the foundation everything else in the project reads from: a
synthetic raw telemetry generator + a feature pipeline that turns it into
a versioned, point-in-time, lineage-tagged feature table.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run it

```bash
# 1. Generate synthetic raw telemetry (accounts + events)
python generate_telemetry.py

# 2. Turn telemetry into a feature snapshot as of a given date
python feature_pipeline.py --as-of 2026-09-28

# Or generate a weekly history of snapshots, for later model training:
python feature_pipeline.py --as-of 2026-09-28 --backfill 2026-06-01
```

## What you get in `data/`

| File | What it is |
|---|---|
| `accounts.csv` | Contract facts per account: seats, contract dates, renewal date, segment |
| `events.csv` | Raw event-level telemetry: logins, searches, InMail sends/replies, session duration, support tickets/CSAT, CRM sync status, champion turnover, NPS |
| `features.csv` | The versioned, point-in-time feature table - one row per account per `as_of_date` |
| `feature_lineage.json` | Every feature mapped to its source event type(s) and transform logic |
| `_latent_risk_labels.csv` | Ground-truth risk flag used only to *generate* realistic synthetic behavior - not a feature, not used by the pipeline. Useful later for checking your trained model against ground truth. |

## Why it's built this way

- **`events.csv` is event-level, not pre-aggregated.** Real telemetry never
  arrives as a clean per-account row - it arrives as a firehose of individual
  events. The feature pipeline's whole job is turning that into something
  scoreable.
- **`feature_pipeline.py` never looks past `as_of_date`.** Every window
  (`recent_30d`, `baseline_90d_ago`, etc.) is computed only from events
  before the cutoff. This is what makes a later held-out-period evaluation
  honest instead of leaking the future into the past.
- **Lineage is enforced, not just documented.** Every feature is declared
  in the `LINEAGE` dict before it's computed, and the pipeline raises an
  error if it ever tries to write a feature with no lineage entry. Lineage
  gets written to `feature_lineage.json` alongside the data itself.

## Sanity check it worked

```bash
python -c "
import pandas as pd
feat = pd.read_csv('data/features.csv')
risk = pd.read_csv('data/_latent_risk_labels.csv')
m = feat.merge(risk, on='account_id')
print(m.groupby('_is_latent_risk')[['logins_per_seat_trend_3m','support_csat','champion_turnover_flag']].mean())
"
```
You should see accounts flagged `True` (latent risk) showing lower login
trend, lower CSAT, and more champion turnover than `False` accounts. If
the numbers look flat or reversed, something's off in either the generator
or the pipeline's windowing.

## Next step

Step 2 is the scoring service: train a baseline model on `features.csv`
(joined against `_latent_risk_labels.csv` as ground truth), wrap it in an
API that returns `score`, `risk_band`, and `contributing_signals` per the
contract shape, and start building the UI on top of that response - a
dashboard that lists accounts, lets you filter by risk band, and drills
into the signals behind any one score.
