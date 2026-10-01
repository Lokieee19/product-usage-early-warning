import { useEffect, useState } from "react";
import { Activity, CircleHelp, RefreshCw, ShieldCheck } from "lucide-react";
import { Badge, Spinner } from "./components";
import { getDrift, getModelPerformance } from "./lib/api";
import "./Evaluation.css";

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
const isRate = (value) => isNumber(value) && value >= 0 && value <= 1;
const percent = (value) => isRate(value) ? `${(value * 100).toFixed(1)}%` : "Not available";
const displayMetric = (value) => value != null && Number.isFinite(Number.parseFloat(String(value))) ? String(value) : "Not available";

function GateBadge({ value }) {
  return <Badge tone={value === true ? "success" : value === false ? "warning" : "neutral"}>
    {value === true ? "Passed" : value === false ? "Needs review" : "Not reported"}
  </Badge>;
}

export default function Evaluation() {
  const [reload, setReload] = useState(0);
  const [state, setState] = useState({ loading: true, error: null, report: null, drift: null });

  useEffect(() => {
    let active = true;
    setState({ loading: true, error: null, report: null, drift: null });
    Promise.all([getModelPerformance(), getDrift()])
      .then(([report, drift]) => {
        if (!report || !Array.isArray(report.metrics) || !drift || !Array.isArray(drift.signals)) {
          throw new Error("Invalid report response");
        }
        if (active) setState({ loading: false, error: null, report, drift });
      })
      .catch(() => {
        if (active) setState({ loading: false, error: "Evaluation reports could not be loaded. Check the scoring API and its saved evaluation and drift reports, then retry.", report: null, drift: null });
      });
    return () => { active = false; };
  }, [reload]);

  const { loading, error, report, drift } = state;
  const metrics = Object.fromEntries((report?.metrics ?? []).map((metric) => [metric.label, metric.value]));
  const withPlay = report?.playEffectiveness?.churn_rate_with_play;
  const withoutPlay = report?.playEffectiveness?.churn_rate_without_play;
  const difference = isRate(withPlay) && isRate(withoutPlay) ? (withoutPlay - withPlay) * 100 : null;
  const gateChecks = [
    { name: "Risk ranking", rule: "AUROC ≥ 0.75", value: report?.gateChecks?.ranking_quality_ok, scope: "Included in saved gate" },
    { name: "Drift validation", rule: "Synthetic drift accuracy ≥ 60%", value: report?.gateChecks?.drift_monitor_validated, scope: "Included in saved gate" },
    { name: "Attribution coverage", rule: "Coverage ≥ 100%", value: isNumber(report?.attributionCoverage) ? report.attributionCoverage >= 1 : null, scope: "Additional display check" },
    { name: "Lookup latency estimate", rule: "Estimated p95 < 50 ms", value: isNumber(report?.p95LatencyMs) ? report.p95LatencyMs < 50 : null, scope: "Additional display check" },
  ];

  return <div className="evaluation-page">
    <div className="evaluation-toolbar">
      <Badge tone="purple">Saved reports · synthetic demonstration</Badge>
      <button className="button" onClick={() => setReload((value) => value + 1)} disabled={loading}><RefreshCw size={15} />{loading ? "Loading reports…" : "Reload reports"}</button>
    </div>
    <div className="evaluation-notice"><CircleHelp size={20} /><p><strong>Results, not a new evaluation run.</strong> This page reads saved backend reports. Reloading fetches those reports again; it does not retrain the model or run evaluation. The project uses synthetic risk labels and simulated outcomes—not verified production results.</p></div>

    {loading ? <Spinner label="Loading evaluation reports…" /> : error ? <section className="panel evaluation-section" role="alert"><h2>Reports unavailable</h2><p>{error}</p><button className="button" onClick={() => setReload((value) => value + 1)}>Retry reports</button></section> : <>
      <div className="evaluation-metrics">
        <section className="panel evaluation-metric"><span>Risk-ranking quality</span><strong>{displayMetric(metrics["Risk ranking quality"])}</strong><small>AUROC · target ≥ 0.75</small></section>
        <section className="panel evaluation-metric"><span>Attribution coverage</span><strong>{percent(report.attributionCoverage)}</strong><small>Recognized top-signal labels</small></section>
        <section className="panel evaluation-metric"><span>Lookup latency estimate</span><strong>{isNumber(report.p95LatencyMs) ? `${report.p95LatencyMs.toFixed(2)} ms` : "Not available"}</strong><small>p95 · includes fixed 4 ms overhead</small></section>
        <section className="panel evaluation-metric"><span>Input drift alerts</span><strong>{isNumber(drift.nFeaturesAlerting) ? drift.nFeaturesAlerting : "Not available"}</strong><small>Drift snapshot · {drift.asOfDate ?? "Not reported"}</small></section>
      </div>

      <section className="panel evaluation-section">
        <div className="evaluation-heading"><div><h2>How we evaluate</h2><p>The question, the calculation, and the limits of each result.</p></div><ShieldCheck size={22} /></div>
        <div className="table-scroll"><table className="evaluation-table"><thead><tr><th scope="col">What we check</th><th scope="col">How it is calculated</th><th scope="col">Saved result</th><th scope="col">What it does not prove</th></tr></thead><tbody>
          <tr><th scope="row">Model risk ranking</th><td>Join account scores to synthetic latent-risk labels and calculate AUROC on the scored cohort.</td><td>{displayMetric(metrics["Risk ranking quality"])}</td><td>Not accuracy, calibrated churn probability, or independent future-period validation.</td></tr>
          <tr><th scope="row">Explanation coverage</th><td>Of the evaluated top signals, count the share mapped to a known human-readable feature label.</td><td>{percent(report.attributionCoverage)}</td><td>Does not validate causal explanations; accounts with no top signal are not counted in this calculation.</td></tr>
          <tr><th scope="row">Serving-path estimate</th><td>Time cached score lookups, add a fixed 4 ms overhead to each, and take the 95th percentile.</td><td>{isNumber(report.p95LatencyMs) ? `${report.p95LatencyMs.toFixed(2)} ms` : "Not available"}</td><td>Not measured HTTP latency, browser performance, or on-demand model inference time.</td></tr>
          <tr><th scope="row">Drift detection validation</th><td>Read detection accuracy from the synthetic drift-injection validation report.</td><td>{displayMetric(metrics["Drift alert accuracy"])}</td><td>Does not guarantee that every real-world change will be detected.</td></tr>
        </tbody></table></div>
        <p className="evaluation-footnote">Evaluation source: saved outcomes evaluation report. Its model version and evaluation timestamp are not exposed by this API response; the global footer refers to the score snapshot, not evaluation freshness.</p>
      </section>

      <section className="panel evaluation-section">
        <h2>Playbook effectiveness</h2><p>For Critical and High accounts, join logged actions with outcomes and compare the churn rate where an action timestamp exists versus where it does not.</p>
        <div className="evaluation-comparison">
          {[{ label: "With a recorded play", value: withPlay }, { label: "Without a recorded play", value: withoutPlay }].map(({ label, value }) => <div key={label}><span>{label}</span><strong>{percent(value)}</strong><div className="evaluation-rate-track" aria-hidden="true"><span style={{ width: `${isRate(value) ? value * 100 : 0}%` }} /></div><small>Simulated churn rate</small></div>)}
        </div>
        <p className="evaluation-difference">{difference === null ? "A comparison requires both churn rates; one or both are not available." : difference === 0 ? "No observed difference between the reported churn rates." : `${Math.abs(difference).toFixed(1)} percentage points ${difference > 0 ? "lower" : "higher"} churn with a recorded play.`}</p>
        <p className="evaluation-footnote">Descriptive comparison of simulated outcomes—not proof that the play caused a reduction. Group sizes, confidence intervals, and randomized assignment evidence are not supplied here. Browser-local launches and outcome edits are not included in this report.</p>
      </section>

      <section className="panel evaluation-section">
        <div className="evaluation-heading"><div><h2>Input data drift</h2><p>Population Stability Index (PSI) compares current feature distributions with their stored baseline. Larger values indicate greater change—not necessarily poorer model quality.</p></div><Activity size={22} /></div>
        <p className="evaluation-footnote">Report date: {drift.asOfDate ?? "Not reported"} · Reported review threshold: {isNumber(drift.alertThreshold) ? drift.alertThreshold : "Not reported"}. Status is taken from each feature's saved alert flag.</p>
        {drift.signals.length ? <div className="table-scroll"><table className="evaluation-table"><thead><tr><th scope="col">Input signal</th><th scope="col">PSI</th><th scope="col">Status</th></tr></thead><tbody>{drift.signals.map((signal) => <tr key={signal.feature}><th scope="row">{signal.name}</th><td>{isNumber(signal.psi) ? signal.psi.toFixed(4) : "Not available"}</td><td><Badge tone={signal.alert === true ? "warning" : signal.alert === false ? "success" : "neutral"}>{signal.alert === true ? "Review drift" : signal.alert === false ? "Stable" : "Not reported"}</Badge></td></tr>)}</tbody></table></div> : <p>No feature-level drift results were supplied.</p>}
      </section>

      <section className="panel evaluation-section">
        <div className="evaluation-heading"><div><h2>Evaluation checks</h2><p>The saved aggregate gate combines ranking quality and drift validation only.</p></div><Badge tone={report.gate === "passed" ? "success" : report.gate === "failed" ? "warning" : "neutral"}>Saved gate: {report.gate === "passed" ? "passed" : report.gate === "failed" ? "failed" : "not reported"}</Badge></div>
        <div className="table-scroll"><table className="evaluation-table"><thead><tr><th scope="col">Check</th><th scope="col">Current criterion</th><th scope="col">Result</th><th scope="col">Gate scope</th></tr></thead><tbody>{gateChecks.map((check) => <tr key={check.name}><th scope="row">{check.name}</th><td>{check.rule}</td><td><GateBadge value={check.value} /></td><td>{check.scope}</td></tr>)}</tbody></table></div>
        <p className="evaluation-footnote">Display only: these checks do not trigger or block deployments. Current criteria reflect the project's evaluation code, not configurable thresholds returned by the API.</p>
      </section>
      <section className="evaluation-notice"><CircleHelp size={20} /><div><h2>What is not evaluated here?</h2><ul><li>A complete data-quality audit of missing values, duplicates, schema validity, or invalid records.</li><li>Independent temporal holdout results, production customer outcomes, or causal playbook impact.</li><li>Automatic retraining, CI release enforcement, canary deployment, or rollback readiness.</li></ul></div></section>
    </>}
  </div>;
}