# Signal — churn early-warning dashboard

A customer-intelligence UI, connected live to the `churn-scoring` API (accounts,
scores, signals, playbooks, drift, and evaluation metrics all come from the
real backend — nothing here is fixture data).

## Setup

```bash
npm install
npm run dev
```

Open the printed localhost URL. The API base URL is read from `.env`
(`VITE_API_BASE_URL`, defaults to `http://localhost:8000`). Start the backend
first:

```bash
cd ../churn-scoring
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

If `data/scores_latest.json` doesn't exist yet, run `python score.py` first
(and `python ../churn-outcomes/evaluate.py`, `python ../churn-monitoring/drift_monitor.py`
for the Monitoring page's real numbers).

## Pages

- **Overview** — portfolio metrics, risk history, risk distribution (live,
  4-band: Critical/High/Medium/Low), and recommended playbooks.
- **Accounts** — search, risk/plan/industry filters, sorting, pagination,
  empty states, and a filtered CSV export.
- **Account details** — risk score, real top-contributing signals, a 90-day
  login trend, renewal info, and the policy's recommended playbook.
- **Playbooks** — the real interventions from `churn-policy/plays.yaml`.
- **Activity log** — the real `churn-outcomes/data/actions_log.csv` feed,
  merged with anything you launch this session.
- **Monitoring** — real model-quality metrics (`churn-outcomes/evaluate.py`),
  real feature drift/PSI (`churn-monitoring/drift_monitor.py`), and the real
  risk-band distribution.
- **Settings** — compact rows and renewal reminders (browser-local only).

## What's live vs. session-only

Everything you see reading data is live from the backend. The one thing that
isn't yet: launching a playbook or recording an outcome only writes to this
browser's `localStorage` — there's no `POST` endpoint on `churn-scoring/api.py`
to write those back to `churn-outcomes/data/actions_log.csv` yet. The UI is
explicit about this wherever it applies (see the "This session" badges in the
Activity log, and the notices in the Launch/Outcome forms).

## Adding new endpoints

`src/lib/api.js` is the only file that knows about `fetch` and the API base
URL. If you add an endpoint to `churn-scoring/api.py`, add a matching export
there and call it from `App.jsx` alongside the existing `Promise.all([...])`
load — every other component just receives plain props and has no idea a
backend exists.
