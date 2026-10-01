# Signal — Dashboard Feature and User Guide

**Documented:** September 30, 2026  
**Scope:** Current implementation, including the icon-only sidebar, teal/slate theme, and removal of the duplicate account table from Overview.

> **Navigation update:** The former Monitoring tab has been replaced by **Evaluation**, which explains the methodology, saved results, and limitations. Evaluation also shows playbook effectiveness. The old Monitoring section below is retained as historical reference. “Monitoring” remains a valid activity outcome status.

## Evaluation tab — current interface

The Evaluation icon opens a dedicated page that requests model-performance and drift reports when entered. It does not run the underlying evaluation scripts. Request failures remain within this page and show a retry control rather than replacing other tabs.

| Section | What it shows |
|---|---|
| Summary cards | AUROC, attribution coverage, estimated p95 lookup latency, and feature drift alert count |
| How we evaluate | For each metric: the question being checked, calculation method, saved result, and interpretation limits |
| Playbook effectiveness | Simulated churn rates with and without a recorded play for Critical/High accounts, plus the difference in percentage points |
| Input data drift | Report date, PSI threshold, and per-feature PSI/status from the saved report |
| Evaluation checks | Aggregate saved gate plus ranking, drift-validation, attribution, and latency checks, with explicit gate membership |
| What is not evaluated here? | Missing full data-quality audit, independent temporal validation, causal proof, and automated production-release enforcement |

**Reload reports** fetches saved reports again, without retraining or regenerating results. Missing comparison values display “Not available” rather than zero. Local browser launches/outcomes do not update these results. The page identifies the latency as a cache-lookup estimate with fixed overhead and all results as synthetic/simulated demonstration evidence. The evaluation timestamp/model version are not exposed by this API response; the footer's score-snapshot date does not establish evaluation freshness.

The Evaluation page does not restore the former Monitoring screen's duplicate score-distribution view; the portfolio distribution remains on Overview. Backend services are unchanged.

## Contents

1. [Purpose and implementation status](#1-purpose-and-implementation-status)
2. [Navigation and common controls](#2-navigation-and-common-controls)
3. [Overview](#3-overview)
4. [Accounts](#4-accounts)
5. [Account intelligence drawer](#5-account-intelligence-drawer)
6. [Playbooks](#6-playbooks)
7. [Monitoring](#7-monitoring)
8. [Activity log](#8-activity-log)
9. [Settings](#9-settings)
10. [Help, workspace, and implementation dialogs](#10-help-workspace-and-implementation-dialogs)
11. [Data sources and technical flow](#11-data-sources-and-technical-flow)
12. [Suggested user workflow](#12-suggested-user-workflow)
13. [Limitations and interpretation notes](#13-limitations-and-interpretation-notes)
14. [Glossary](#14-glossary)

## 1. Purpose and implementation status

Signal is a customer-churn early-warning dashboard for Customer Success teams. It helps answer four questions:

- **Who needs attention?** Review risk bands and account scores.
- **Why?** Inspect product usage, support, relationship, and renewal signals.
- **What should we do?** Follow a recommended intervention playbook.
- **What happened afterward?** Record a local outcome and review the action timeline.

### What “live” means here

The interface calls a running API rather than displaying a hardcoded frontend account list. However, most API responses read previously generated files and score snapshots. “LIVE” does **not** mean continuous streaming, automatic rescoring, or a production customer-data connection.

The project includes synthetic telemetry generation and simulated outcomes. API-backed records and evaluation results must therefore not be presented as independently verified production customer behavior.

| Capability | Current implementation |
|---|---|
| Read account scores, signals, policies, evaluation, and drift | Implemented through API requests |
| Search, filter, sort, and paginate accounts | Implemented in the browser |
| View account-specific recommendations | Implemented through the policy layer |
| Export account data | Implemented as a CSV download |
| Launch a playbook | Creates a browser-local activity record |
| Record an outcome | Updates a browser-local activity record |
| Send emails, create support tickets, or update a CRM | Not implemented |
| Persist dashboard actions to the backend | Not implemented |
| Authentication, roles, and team/workspace management | Not implemented |
| Automatic background refresh or streaming | Not implemented |

## 2. Navigation and common controls

### 2.1 Icon-only sidebar

The sidebar uses icons instead of visible tab names. Hover labels and accessible button names identify the controls. The selected tab is highlighted.

| Control | What it does |
|---|---|
| Signal logo | Returns to Overview |
| Workspace/layers icon | Opens the “Your workspace” information dialog |
| Overview | Opens portfolio-level risk metrics and charts |
| Accounts | Opens the complete searchable account table |
| Playbooks | Opens the intervention catalog |
| Evaluation | Explains evaluation methods, saved results, playbook comparisons, drift, and limitations |
| Activity log | Opens backend and browser-local customer actions |
| Settings | Opens browser preferences and local-activity reset |
| Help/question mark | Opens the getting-started and risk-band guide |
| Profile/fingerprint icon | Opens the same workspace dialog |

On small screens, a menu button opens the sidebar. Clicking its backdrop, selecting a page, or pressing Escape closes it. Page navigation is maintained in application state; reloading starts on Overview rather than restoring a tab-specific URL.

### 2.2 Global account search

- Matches account **name**, **industry**, and **top signal**.
- Is case-insensitive and ignores leading/trailing spaces.
- Combines with the selected risk band, plan, and industry filters.
- Pressing **Ctrl+K** on Windows or **Cmd+K** on macOS focuses the input.
- Typing from Playbooks, Evaluation, Activity log, or Settings navigates to Accounts.
- Typing on Accounts filters the table in place.
- **Current caveat:** typing on Overview stays on Overview, even though that page no longer has an account table. Open Accounts to see the results. The query still affects exports.

Search and filter selections persist in memory when switching tabs. They are not saved as user preferences across reloads.

### 2.3 Export report

Available on Overview and Accounts.

1. Applies the current search, risk-band, plan, industry, and sort selections.
2. Exports **all matching accounts**, not just the six rows on the current page.
3. Downloads a CSV containing account name, score, band, ARR in USD, usage change, top signal, industry, plan, and renewal date.
4. Shows a temporary confirmation with the exported account count.

CSV fields are quoted and escaped; formula-like leading characters are guarded against spreadsheet interpretation. The file includes a UTF-8 byte-order mark for spreadsheet compatibility.

**Important:** Overview's metrics always describe the full portfolio, but its export can use filters left over from Accounts. Export is not a PDF or a download of the charts.

### 2.4 Notifications

The bell opens a small notification panel:

- A customer-risk item uses the first Critical account in the loaded, score-sorted account list. Selecting it opens that account's detail drawer.
- An informational drift item displays the reported number of drift alerts when the count is greater than zero; it does not navigate to another tab.
- “Mark all as read” hides the unread indicator and shows a confirmation.

This is not a push-notification system. There is no server-backed inbox, email delivery, or persistent read history. The read flag resets on reload.

### 2.5 Profile, footer, and feedback

- The **CS** avatar opens workspace information, not an authenticated personal profile.
- The footer shows the score snapshot date received from the metadata API.
- The **LIVE** badge indicates API-backed presentation, not a freshness guarantee.
- Toast messages report actions such as export, launch, outcome save, and storage failures; they disappear after approximately 4.5 seconds.
- The interface supports keyboard focus indicators and a “Skip to content” link.

## 3. Overview

**Purpose:** Provide a quick portfolio-level summary before the user investigates individual customers.

The former **“Accounts to keep an eye on”** table has been removed. Account rows are now shown only under Accounts.

### 3.1 Attention banner

The banner displays the number of **Critical** accounts and offers “Review at-risk accounts.” Selecting it opens Accounts, clears other filters, and selects the Critical band.

Although the button says “at-risk,” this shortcut selects Critical only—not Critical plus High.

### 3.2 Summary cards

| Card | What it measures | Interpretation |
|---|---|---|
| Monitored accounts | Number of accounts returned by the account-list API | Size of the loaded scored portfolio |
| Critical accounts | Number in the Critical band, plus percentage of the portfolio | Highest-priority review queue; arrow opens Critical accounts |
| ARR at risk | Total estimated annual revenue for Critical and High accounts | Revenue associated with elevated-risk customers, not guaranteed lost revenue |
| Healthy accounts | Number in the Low band and percentage of the portfolio | Lower-risk customers according to the current scoring snapshot |

**Revenue calculation:** the API estimates account ARR as contracted seats × USD 600 per year × segment multiplier. Multipliers are SMB 1.0, Midmarket 1.3, and Enterprise 1.8. This is a project pricing assumption, not an integration with billing or actual booked contract revenue.

**Sparkline caveat:** the small chart in “Monitored accounts” uses historical at-risk counts. It is not a historical series of total account count.

### 3.3 The health of your portfolio

The area chart plots the number of **Critical plus High** accounts at each historical scoring snapshot.

- Horizontal axis: snapshot date.
- Vertical axis: number of at-risk accounts.
- Hover tooltip: date and count.
- Source: cached historical scoring results.

A rising line means more accounts crossed into these risk bands. It does not show actual cancellations, verified churn events, or the causal effect of a playbook.

### 3.4 Risk, at a glance

The donut shows the latest distribution across Critical, High, Medium, and Low risk.

- Center: total accounts.
- Legend: each band's count and percentage.
- Selecting a legend entry opens Accounts with that band selected and clears other filters.
- The detail arrow opens Accounts with all bands selected.

### 3.5 A next step worth taking

Shows the first two entries in the playbook catalog. Each item includes its name, category, and step count.

- Selecting a play opens its account-selection/launch form.
- “All playbooks” opens the full catalog.

These two items are selected by catalog order. They are not ranked by expected business impact or personalized to the current portfolio.

### 3.6 A healthy foundation

| Item | Current behavior |
|---|---|
| Scoring API — Operational | Fixed display text, not an independent health probe |
| Feature pipeline — Up to date | Fixed display text, not a measured freshness check |
| Input drift | Uses the actual alert count from the drift report |

## 4. Accounts

**Purpose:** Find, prioritize, and inspect individual customer accounts.

### 4.1 Portfolio strip

Shows total loaded accounts, summed estimated ARR, and the number of Critical accounts needing attention. These totals describe the complete loaded portfolio rather than the filtered table result.

### 4.2 Your accounts table

| Column | Meaning and behavior |
|---|---|
| Account | Company name and plan/segment; selecting the name opens account intelligence |
| Risk score | A 0–100 risk-ranking score plus change from the previous scoring snapshot |
| ARR | Estimated annual account revenue, displayed in compact USD notation |
| Usage trend (30d) | Change in login volume for the latest 30 days versus the preceding 30 days |
| Top signal | Human-readable name of the strongest model-attribution feature |
| Industry | Account industry classification |
| Arrow action | Opens the same account intelligence drawer |

Avatar colors are stable decorative colors derived from account ID. They do not indicate risk, segment, or account ownership.

### 4.3 Risk scores and bands

The stored model configuration currently uses:

| Band | Score range | API urgency guidance |
|---|---|---|
| Critical | 70–100 | Immediate action recommended |
| High | 40–69 | Action recommended this week |
| Medium | 15–39 | Monitor closely; no urgent action yet |
| Low | 0–14 | No action needed |

Scores are generated by scaling the model's raw margin to 0–100 against stored training-time bounds. A score of 80 does **not** mean an 80% probability of churn. Band boundaries can change with model configuration.

The score-cell styling uses three visual ranges (70+, 40–69, below 40), while the actual risk taxonomy has four bands. Consequently, a greenish numeric score is not sufficient to distinguish Medium from Low; use the actual band/filter or detail badge.

The score delta is the latest minus previous snapshot score, in points. Positive means risk increased; negative means it decreased. It is not the same as the usage percentage.

### 4.4 Risk tabs and filters

- **All accounts:** no risk-band restriction.
- **Critical / High / Medium / Low:** exact band filtering.
- **Critical count badge:** total Critical accounts in the portfolio, not just the current search results.
- **Filters button:** opens or hides additional plan, industry, and sorting controls.
- **Plan:** restricts to a segment label such as SMB, Midmarket, or Enterprise.
- **Industry:** restricts to a specific industry.
- **Highest risk:** sorts by descending score; this is the default.
- **Highest ARR:** sorts by descending estimated revenue.
- **Soonest renewal:** sorts by days remaining, putting missing renewal values last.
- **Risk score header:** restores highest-risk sorting; it does not toggle ascending order.
- **Reset filters:** clears search and restores all bands/plans/industries, highest-risk sorting, and page one.
- **Clear search:** removes only the search text.

Plan and industry options are derived from the loaded account data. The indicator dot on Filters reflects non-default plan or industry, not all possible active filters.

### 4.5 Pagination and empty states

- Six accounts appear per page.
- At most ten numbered page buttons appear at a time: 1–10, then 11–20, and so on.
- Previous/Next move one page at a time; crossing a group boundary changes the displayed numbers.
- The footer shows the visible row range and total filtered account count.
- Changing band, plan, industry, or sort resets the page to one.
- Search changes do not explicitly reset pagination; the current page is limited to the available page count.
- If no records match, an empty state offers “Clear filters.”

### 4.6 How risk is scored

Opens the general risk-band/workflow guide. It is an introductory explanation, not a complete model-training report or a live scoring debugger.

## 5. Account intelligence drawer

**Purpose:** Explain an individual account's risk and provide a next action.

Opening the drawer makes an additional API request for the selected account. It does not automatically retrain or rescore the account.

### 5.1 Identity and summary

Displays company name, industry, plan, risk band, 0–100 score, score change, estimated ARR, renewal date, and urgency guidance.

### 5.2 Renewal reminder

If the renewal-reminders preference is enabled and days to renewal is 30 or less, a reminder appears. The current condition also includes overdue renewals, so negative day counts are possible. This is an on-screen highlight, not a scheduled reminder or email.

### 5.3 What's driving the score

Lists the top contributing features and their relative importance bars.

These are based on absolute SHAP attribution magnitudes. The top-signal percentages are normalized among the selected top signals. They explain what the model relied on, not proof that a feature caused churn. Magnitude alone does not indicate whether a feature pushed risk upward or downward.

### 5.4 Product engagement

Shows login activity over a 90-day period, grouped into six periods, plus the latest 30-day usage-change percentage.

The chart uses average daily login-event values within each period. The percentage compares recent and previous 30-day sums using a denominator of absolute previous sum plus one; the result is clipped to −100% to +100%. It is therefore a bounded project indicator, not an unrestricted standard growth-rate calculation.

### 5.5 Signal attribution

The attribution table includes:

- Feature/signal name.
- Its share of total absolute model attribution.
- Current feature value compared with its stored baseline mean.

These percentages use a different denominator from the top-signal bars, so they need not match. The UI prefixes contributions with “+”, but the backend supplies magnitude shares, not signed contributions or additive score points.

### 5.6 Recommended play

- Critical and High accounts are eligible for a feature-specific recommendation.
- The strongest contributing feature determines the playbook through configured rules.
- Medium and Low accounts receive the default “Monitor” recommendation.
- An unmapped feature also falls back to Monitor.
- Monitor shows normal check-in guidance without a launch button.

For a non-default recommendation, the drawer's launch button records the action directly for this account; it does not open an account selector. Any locally stored In progress action for that account disables this drawer button, even if that action uses another playbook.

## 6. Playbooks

**Purpose:** Turn risk signals into human-led retention action plans.

Playbooks are predefined policy rules and checklists. They are not generated by a language model, and they do not perform customer outreach automatically.

### 6.1 Playbook cards

Each card shows an icon, broad risk label, category, name, trigger signals, ordered steps, and a launch button. The catalog excludes the default Monitor entry.

The High risk / Medium-high risk badges are assigned by playbook type. They are not a live eligibility check for a selected customer.

### 6.2 Current catalog and steps

| Playbook | Relevant signals | Configured steps |
|---|---|---|
| Usage recovery | Login decline; session-duration decline | 1. Contact account within 3 days. 2. Review abandoned features with the account team. 3. Offer a product enablement session. |
| Seat utilization review | Active-seat percentage; seat utilization versus contracted seats | 1. Audit inactive teams/seats. 2. Propose a seat rebalance or true-up conversation. 3. Share a usage benchmark versus similar accounts. |
| Feature re-engagement | Search trend; InMail send trend; InMail response rate | 1. Identify core workflows that dropped off. 2. Send a targeted walkthrough. 3. Offer a workflow audit call. |
| Support escalation review | Support-ticket volume; support CSAT | 1. Escalate open tickets to a senior engineer. 2. Schedule a CSAT recovery call. 3. Flag the account to Customer Success leadership. |
| Re-establish champion relationship | Champion-turnover flag | 1. Identify the new day-to-day contact. 2. Schedule an introductory relationship-rebuilding call. 3. Re-share onboarding/value materials. |
| Restore CRM sync | CRM sync activity | 1. Confirm why sync was disabled. 2. Help the administrator re-enable it. 3. Monitor sync for 30 days after the fix. |
| NPS recovery outreach | Latest NPS survey | 1. Follow up personally. 2. Document the root complaint. 3. Route to Support, Product, or Customer Success. |
| Renewal risk escalation | Days to renewal | 1. Involve the account executive immediately. 2. Prepare a leadership risk brief. 3. Schedule an executive check-in before renewal. |

The checklist describes work a human should perform. There is no per-step completion tracking, owner assignment, deadline scheduler, or automated email/ticket execution.

### 6.3 Launch flow from the catalog

1. Select “Launch playbook.”
2. Review the playbook category, trigger, and steps.
3. Choose an account in the dropdown.
4. Submit the form.
5. A new local activity is created with status In progress, launch time, and an initial note.

The dropdown contains all loaded accounts and initially selects the first account in API order (highest score first). It does not restrict the options to accounts that meet that playbook's recommendation rules.

Submitting the same account/playbook combination is blocked if that combination already has a local In progress action. Completed/other statuses do not block a later launch. This check does not inspect backend activity for duplicates.

### 6.4 Persistence and actual effect

Launching stores an entry in browser local storage. It does not change the risk score, write to the backend action log, send a message, create a CRM task, or start a timed workflow.

## 7. Monitoring

**Removed from navigation:** This section documents the former screen for reference. These controls are no longer accessible in the current website; backend evaluation and drift reports remain available.

**Purpose:** Inspect model ranking quality, explanation coverage, scoring-path estimates, and changes in input distributions.

Both model-performance and drift reports are needed to populate this page.

### 7.1 Metric cards

| Metric | What it means | Current implementation |
|---|---|---|
| Risk-ranking quality | AUROC: ability to rank risk-labelled accounts above other accounts | Read from the evaluation artifact; evaluated against synthetic latent-risk labels |
| Signal attribution | Share of evaluated top signals that map to recognized feature labels | Displayed as a percentage; not a measure of causal explanation correctness |
| Scoring latency | p95 lookup-path latency estimate | Times cached dictionary lookups and adds a fixed 4 ms overhead; not measured browser-to-server latency |
| Drift alerts | Number of input features marked as shifted | Read from the drift report |

The ranking card's “Gate passed/failed” text reflects the evaluation report's aggregate gate, not only AUROC. “Complete · live” and “p95 · cache-served” are display labels rather than independent health checks.

### 7.2 Input drift tab

Shows the latest feature drift report, sorted by decreasing Population Stability Index (PSI).

| Field | Meaning |
|---|---|
| Input signal | Human-readable feature name |
| PSI | Difference between baseline and current feature distributions |
| Distribution shift | Visual meter, scaled from PSI and capped at full width |
| Status | Stable or Review drift, using the report's alert flag |

When alerts exist, a banner displays their count, review threshold, and report date. Larger PSI indicates more distribution change; it does not by itself prove a model has become inaccurate or that customers have churned.

This page reads a prepared report. It does not run drift analysis, inject drift, retrain a model, or dismiss an alert.

### 7.3 Score distribution tab

Displays counts for the current Critical, High, Medium, and Low bands. Bar widths use each band's percentage of the portfolio. This is another view of the same latest distribution shown by Overview's donut, not a historical comparison.

### 7.4 Release gates tab

| Check | Current criterion/source |
|---|---|
| Ranking quality | Stored evaluation check; current evaluation threshold AUROC ≥ 0.75 |
| Drift monitor validated | Stored validation check; current evaluation threshold drift accuracy ≥ 60% |
| Attribution | UI checks attribution coverage ≥ 100% |
| Latency | UI checks reported p95 < 50 ms |
| Temporal holdout / rollback | Presented as future automation, not completed checks |

The evaluation report's aggregate gate currently combines ranking quality and drift validation. It does not incorporate every additional row shown by the UI.

Passing these displayed checks does not deploy a model or block a release automatically. There is no connected CI gate, canary rollout, or automatic rollback. “View implementation notes” opens the project roadmap dialog.

## 8. Activity log

**Purpose:** Review customer-intervention records and update the outcomes of locally launched plays.

### 8.1 Timeline sources

The timeline combines:

1. All locally stored launches, newest launches first.
2. Up to 20 recent API-provided actions from the backend outcomes log.

Local entries appear first as a group. The combined list is not globally re-sorted by time. Backend entries are sorted by action timestamp, falling back to scoring timestamp.

The project includes simulated outcome/action generation. A backend entry such as “Contacted customer” describes a stored log record; the dashboard did not itself perform that contact.

### 8.2 Summary badges

- **Actions:** count of currently loaded local plus backend records, not the complete historical backend total.
- **In progress:** records whose status is exactly In progress.
- **Completed:** records with status Completed or Retained.

### 8.3 Individual timeline entries

Each entry shows the playbook, status, account, note/action description, and launch/action time. Local entries carry a “This session” badge. Selecting the account name opens account intelligence.

“This session” is UI wording: local storage can retain the record across reloads and browser restarts until explicitly cleared.

### 8.4 Record outcome

Available only on local entries.

1. Open “Record outcome.”
2. Select In progress, Monitoring, Retained, or Churned.
3. Enter a required nonblank note, up to 1,000 characters.
4. Save to update the local status and note.

Saving does not change the original launch timestamp, append a separate audit event, update backend outcomes, modify risk scores, or recalculate evaluation metrics. Retained and Churned are user-entered labels, not independently verified business outcomes.

Backend entries are read-only in this UI. Their statuses can include Pending, In progress, and Completed, which differ from the local outcome form's choices.

### 8.5 Header launch shortcut

“Launch a playbook” opens the launch form for the first catalog play. It does not provide a separate playbook selector; use the Playbooks tab to choose another play.

## 9. Settings

**Purpose:** Adjust local display preferences and manage browser-local actions.

### 9.1 Compact account rows

Reduces account-table row spacing. It does not change the six-row page size, account data, risk model, or layout of other pages. Default: off.

### 9.2 Renewal reminders

Controls the ≤30-day highlight in account intelligence. Default: on. It does not send notifications or schedule reminders.

### 9.3 Automatic preference saving

Preferences are stored under `churn-preferences-v1` in local storage and apply to this browser/site origin only. Another browser, device, or origin does not automatically share them.

If storage is unavailable, changes work in memory for the current page session and a warning explains that persistence failed.

### 9.4 Reset session activity

Opens a confirmation dialog. Confirming clears the local playbook-action list stored under `churn-actions-v1`.

- Does not remove backend action records.
- Does not change account scores, monitoring reports, or model artifacts.
- Does not reset display preferences.
- Does not offer undo.

### 9.5 What's next?

“View implementation notes” opens a roadmap describing connected read paths and missing production features. It does not run setup, update services, or execute deployments.

## 10. Help, workspace, and implementation dialogs

### Getting started / How risk is scored

Explains the four risk bands and the workflow: find an account, inspect signals, launch a play, and record an outcome. It also states that launches and outcomes remain local until backend write-back is implemented.

The help text's Critical guidance says to prioritize a check-in this week, whereas account-detail urgency says immediate action. Treat the API urgency and actual business process as the more specific guidance; the wording is not fully aligned.

### Your workspace

Shows the workspace name, API-connection label, and current model version, with a button to open Settings. It explicitly notes that authentication and team management are not connected. There is no actual workspace switcher or user-account editor.

### From prototype to production

Describes telemetry, feature engineering, scoring/API, policy, evaluation, and monitoring. Lists remaining write-back, release-gate automation, canary rollout, and rollback work. These are roadmap statements, not a deployment control panel.

### Dialog interaction

Dialogs provide close buttons, backdrop dismissal, and Escape handling. Keyboard focus is kept inside an open dialog and restored when it closes.

## 11. Data sources and technical flow

### 11.1 Read path

1. Telemetry generation creates account facts and events.
2. Feature processing aggregates telemetry into point-in-time snapshots.
3. Model training and scoring create scores, bands, explanations, and score history.
4. Policy rules map eligible accounts' top signals to playbooks.
5. Evaluation and monitoring generate separate report artifacts.
6. The API reads these artifacts and shapes responses for the dashboard.
7. The browser fetches the responses and renders tabs.

Frontend actions take a separate path: **launch/outcome → browser state → local storage**, not back into the scoring or outcomes pipeline.

### 11.2 API endpoints used by the interface

| Endpoint | Main use |
|---|---|
| `GET /api/summary` | Portfolio summary, including revenue at risk |
| `GET /api/risk-distribution` | Overview donut and Monitoring distribution |
| `GET /api/risk-trend` | Historical at-risk chart |
| `GET /api/accounts` | Account list, search/filter/export, and launch dropdown |
| `GET /api/accounts/{account_id}` | Account intelligence drawer |
| `GET /api/plays` | Catalog and launch checklist |
| `GET /api/recent-actions?limit=20` | Backend portion of Activity log |
| `GET /api/model-performance` | Requested when entering Evaluation or reloading its reports |
| `GET /api/drift` | Drift feature table and alert count |
| `GET /api/meta` | Snapshot date and model version |

An on-demand `GET /api/accounts/{account_id}/rescore` endpoint also exists, but the current dashboard does not call it and provides no rescore button.

The default API base is `http://localhost:8000`, configurable through `VITE_API_BASE_URL`.

### 11.3 Update and error behavior

- Initial data is requested together on application mount.
- There is no polling, automatic retry, websocket stream, or dashboard refresh button.
- Reloading requests the latest available API artifacts again; it does not regenerate them.
- Account details are fetched separately when an account is selected.
- A failure in any required initial request produces the full-page API connection message, even when the actual cause is a missing report or server-side error rather than a stopped API.
- Account-detail failures show a notification; the drawer can remain in its loading presentation.
- Accounts, events, and the model are loaded into API memory at startup. Replacing those underlying inputs can require restarting the API; reloading only the browser is not always enough.

### 11.4 Implementation references

- [Application navigation, state, storage, export, and dialogs](churn-dashboard/src/App.jsx)
- [Overview components](churn-dashboard/src/Dashboard.jsx)
- [Account table and pagination](churn-dashboard/src/AccountsTable.jsx)
- [Playbooks, account detail, activity, and monitoring views](churn-dashboard/src/Views.jsx)
- [Filtering, formatting, and CSV helpers](churn-dashboard/src/data.js)
- [API client](churn-dashboard/src/lib/api.js)
- [API response calculations](churn-scoring/api.py)
- [Scoring and attribution logic](churn-scoring/score.py)
- [Stored model baseline and band cutoffs](churn-scoring/models/feature_baseline.json)
- [Playbook definitions](churn-policy/plays.yaml)
- [Recommendation eligibility and mapping](churn-policy/policy.py)
- [Evaluation calculations](churn-outcomes/evaluate.py)
- [Telemetry and feature-pipeline overview](churn-pipeline/README.md)

## 12. Suggested user workflow

1. **Start with Overview:** review Critical count, estimated ARR at risk, distribution, and history.
2. **Open the priority queue:** choose “Review at-risk accounts” to see Critical accounts.
3. **Narrow the list:** use search, plan, industry, and sort controls.
4. **Inspect an account:** read the score, renewal, attribution, and engagement history.
5. **Choose an intervention:** review the recommended checklist and launch it if appropriate.
6. **Perform the work outside the dashboard:** contact the customer, coordinate support, or hold the renewal discussion.
7. **Record the result:** update the local activity status and note.
8. **Review Evaluation:** inspect methods, saved results, drift, and limitations before relying on scores. Use a separate process for complete data-quality auditing.
9. **Export when needed:** download the filtered account list for discussion or reporting.

## 13. Limitations and interpretation notes

| Do not assume | Actual behavior |
|---|---|
| A score of 80 means 80% churn probability | Score is a scaled model margin |
| API-backed means production customer data | The project includes synthetic telemetry and simulated outcomes |
| LIVE means continuously updated | Most reads use cached/generated artifacts fetched on page load |
| ARR at risk equals expected financial loss | It sums estimated ARR for Critical and High accounts without probability weighting |
| Playbook launch executes the checklist | It creates a browser-local action only |
| Retained means a renewal was verified | It is a locally recorded user status |
| Local outcomes improve the model automatically | No write-back or feedback-driven retraining is connected |
| Service-status text verifies uptime/freshness | Some labels are fixed presentation text |
| p95 latency is measured network performance | It is a lookup benchmark with a fixed overhead estimate |
| Attribution percentages are causal or signed score points | They represent absolute attribution shares |
| Release gates enforce deployment safety | The UI displays checks; automated enforcement is not connected |
| Reset session clears everything | It clears local action records only |

## 14. Glossary

| Term | Meaning |
|---|---|
| Churn | A customer ending or not renewing a relationship/subscription |
| Account | A customer organization represented in the portfolio |
| ARR | Annual recurring revenue; estimated from seat pricing in this project |
| Risk band | Critical, High, Medium, or Low category derived from score cutoffs |
| Snapshot | Data and scores associated with a particular as-of date |
| Top signal | Feature with the strongest absolute contribution to the model output |
| SHAP | Feature-attribution method used to explain model output |
| Playbook | Predefined, human-executed intervention checklist |
| Champion | Main customer contact or internal advocate for the product |
| Seat utilization | Degree to which purchased user capacity is being used |
| CSAT | Customer satisfaction measure, here associated with support |
| NPS | Net Promoter Score survey measure |
| CRM sync | Synchronization with a customer relationship management system |
| AUROC | Ranking-quality metric; not the percentage of correct predictions |
| PSI | Population Stability Index, used to compare feature distributions |
| p95 | Value at the 95th percentile of a set of measurements |
| Local storage | Browser/site-specific persistent storage, not a shared backend database |
| Release gate | A check intended to assess readiness before deployment |