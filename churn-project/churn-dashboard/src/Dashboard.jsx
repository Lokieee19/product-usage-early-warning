import { ArrowRight, ArrowUpRight, ChartNoAxesCombined, Layers, ShieldCheck, Target, Users, Zap } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { SectionHeader } from "./components";

const BAND_CLASS = { Critical: "critical", High: "high", Medium: "medium", Low: "healthy" };

function sparkPath(values) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const scaled = values.map((v) => 4 + ((v - min) / range) * 34);
  const step = 100 / (scaled.length - 1);
  return scaled.map((v, i) => ({ x: i * step, y: 42 - v }));
}

function Metric({ label, value, icon: Icon, caption, trend, color, spark, onClick }) {
  const points = sparkPath(spark);
  return <section className={`panel metric-card metric-${color}`}>
    <div className="metric-label"><span>{label}</span><Icon size={17} /></div>
    <div className="metric-value-row">
      <strong>{value}</strong>
      {points && <svg className="sparkline" viewBox="0 0 100 42" aria-hidden="true">
        <path d={`M0,${points[0].y} ${points.map((p) => `L${p.x},${p.y}`).join(" ")} L100,42 L0,42 Z`} fill="currentColor" opacity=".07" />
        <polyline points={points.map((p) => `${p.x},${p.y}`).join(" ")} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>}
    </div>
    <div className="metric-trend"><span>{color === "green" ? <ArrowUpRight size={13} /> : <span className="tiny-dot" />}{trend}</span>{onClick && <button className="icon-button" aria-label="Review high-risk accounts" onClick={onClick}><ArrowUpRight size={15} /></button>}</div>
    <p>{caption}</p>
  </section>;
}

export function DashboardCharts({ summary, distribution, trend, totalAccounts, viewRisk, viewBand }) {
  const byKey = Object.fromEntries((summary ?? []).map((s) => [s.key, s]));
  const critical = distribution?.find((d) => d.band === "Critical")?.count ?? 0;
  const low = distribution?.find((d) => d.band === "Low")?.count ?? 0;
  const trendValues = (trend ?? []).map((t) => t.value);

  return <>
    <div className="attention-banner">
      <span className="attention-icon"><Zap size={18} /></span>
      <div><strong>A heads-up, not a last-minute surprise.</strong><p>{critical} accounts show early signs of churn in the live scoring run. A timely check-in can make all the difference.</p></div>
      <button onClick={viewRisk}>Review at-risk accounts <ArrowRight size={16} /></button>
    </div>
    <div className="metrics-grid">
      <Metric label="Monitored accounts" value={totalAccounts} icon={Users} caption="Across your live portfolio" trend="All accounts scored" color="violet" spark={trendValues} />
      <Metric label="Critical accounts" value={critical} icon={ShieldCheck} caption="Risk score in the Critical band" trend={byKey.highRisk?.delta ?? ""} color="red" onClick={viewRisk} />
      <Metric label="ARR at risk" value={byKey.revenue?.value ?? "—"} icon={ChartNoAxesCombined} caption={byKey.revenue?.delta ?? "Critical + High bands"} trend="From live account contracts" color="amber" />
      <Metric label="Healthy accounts" value={low} icon={Target} caption="Risk score in the Low band" trend={totalAccounts ? `${Math.round((low / totalAccounts) * 100)}% of portfolio` : ""} color="green" />
    </div>
    <div className="charts-grid">
      <section className="panel trend-panel">
        <SectionHeader title="The health of your portfolio" description="Accounts flagged at risk over time, from the scoring history cache" />
        <div className="chart-legend"><span><i className="legend-dot critical" />At risk</span><span className="legend-period">Recent scoring runs</span></div>
        <div className="area-chart" role="img" aria-label={`Risk trend history ending at ${trendValues.at(-1) ?? 0} accounts at risk`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend ?? []} margin={{ top: 10, right: 6, left: -20, bottom: 0 }}>
              <defs><linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c5525f" stopOpacity={.22} /><stop offset="100%" stopColor="#c5525f" stopOpacity={.03} /></linearGradient></defs>
              <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#ececf4" />
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#858795", fontSize: 10 }} dy={10} minTickGap={20} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#858795", fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #ececf2", fontSize: 12 }} />
              <Area type="monotone" dataKey="value" name="At risk" stroke="#c5525f" fill="url(#riskFill)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-footnote"><span className="live-dot" />Live scoring cache · {totalAccounts} accounts in the latest run</div>
      </section>
      <section className="panel distribution-panel">
        <SectionHeader title="Risk, at a glance" description="Where your accounts stand today" />
        <div className="donut-layout">
          <div className="donut-chart" role="img" aria-label={`${critical} critical, ${(distribution ?? []).find((d) => d.band === "High")?.count ?? 0} high, ${(distribution ?? []).find((d) => d.band === "Medium")?.count ?? 0} medium, ${low} low risk accounts`}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={distribution ?? []} cx="50%" cy="50%" innerRadius={64} outerRadius={84} paddingAngle={5} cornerRadius={4} dataKey="count" nameKey="band" startAngle={90} endAngle={-270} stroke="none">
                  {(distribution ?? []).map((item) => <Cell key={item.band} fill={item.color} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12, border: "1px solid #ececf2" }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center"><strong>{totalAccounts}</strong><span>Total accounts</span></div>
          </div>
          <div className="distribution-legend">
            {(distribution ?? []).map((item) => <button key={item.band} onClick={() => viewBand(item.band)}>
              <i className={`legend-dot ${BAND_CLASS[item.band] ?? "medium"}`} /><span>{item.band}</span><strong>{item.count}</strong><small>{item.pct}%</small>
            </button>)}
          </div>
        </div>
        <div className="distribution-note"><ShieldCheck size={15} /><span>See the why behind every score.</span><button className="icon-button" aria-label="Explore account risk details" onClick={() => viewBand("All accounts")}><ArrowUpRight size={15} /></button></div>
      </section>
    </div>
  </>;
}

export function DashboardBottom({ navigate, onLaunch, plays, driftCount }) {
  return <div className="bottom-grid">
    <section className="panel recommended-panel">
      <SectionHeader title="A next step worth taking" description="Playbooks recommended by the live scoring policy" action="All playbooks" onAction={() => navigate("Playbooks")} />
      <div className="recommended-items">
        {(plays ?? []).slice(0, 2).map((playbook) => <button className="recommended-item" key={playbook.id} onClick={() => onLaunch(playbook.id)}>
          <span className={`playbook-icon ${playbook.color}`}>{playbook.id === "usage_decay" ? <Zap size={19} /> : <Layers size={19} />}</span>
          <span><strong>{playbook.title}</strong><small>{playbook.category} · {playbook.steps.length}-step playbook</small></span>
          <ArrowUpRight size={17} />
        </button>)}
      </div>
    </section>
    <section className="panel health-strip">
      <SectionHeader title="A healthy foundation" description="Live service status" />
      <div className="health-status">
        <span><i className="live-dot" />Scoring API <strong>Operational</strong></span>
        <span><i className="live-dot" />Feature pipeline <strong>Up to date</strong></span>
        <span><i className={driftCount ? "warning-dot" : "live-dot"} />Input drift <strong className={driftCount ? "amber-text" : ""}>{driftCount ? `${driftCount} to review` : "Stable"}</strong></span>
      </div>
    </section>
  </div>;
}
