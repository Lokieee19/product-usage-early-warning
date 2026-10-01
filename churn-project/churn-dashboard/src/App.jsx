import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowUpRight, Bell, Check, ChevronRight, CircleHelp, Download, FileClock, Fingerprint, Layers, LayoutDashboard, Menu, Plus, Radio, Search, Settings, TrendingDown, Users, Workflow } from "lucide-react";
import { accountColor, accountsCsv, filterAccounts, money } from "./data";
import { Badge, Modal, RiskBadge, SectionHeader, StepList, Spinner, Toast } from "./components";
import { DashboardBottom, DashboardCharts } from "./Dashboard";
import AccountsTable from "./AccountsTable";
import Evaluation from "./Evaluation";
import { AccountDetail, ActivityLog, LaunchForm, OutcomeForm, Playbooks } from "./Views";
import * as api from "./lib/api";
import "./App.css";
import "./theme.css";

const navItems = [{ name: "Overview", icon: LayoutDashboard }, { name: "Accounts", icon: Users }, { name: "Playbooks", icon: Workflow }, { name: "Evaluation", icon: Activity }, { name: "Activity log", icon: FileClock }];
const titles = {
  Overview: ["A clearer view of customer health.", "Live signals from the churn-scoring API, updated every scoring run."],
  Accounts: ["Every account. The full picture.", "Know who needs attention, and exactly where to start."],
  Playbooks: ["The right action, at the right time.", "Turn risk signals into meaningful customer conversations."],
  Evaluation: ["Understand the evidence behind the scores.", "What we evaluate, how we measure it, and what the results can tell us."],
  "Activity log": ["Small actions. Lasting impact.", "Live actions from the outcomes log, plus anything you launch this session."],
  Settings: ["Make Signal work for you.", "Manage your personal workspace preferences."],
};
const defaultPreferences = { compact: false, reminders: true };

function readStorage(key, fallback, validate) {
  try { const value = JSON.parse(localStorage.getItem(key)); return validate(value) ? value : fallback; } catch { return fallback; }
}
function validLocalActions(value) {
  return Array.isArray(value) && value.every((a) => a && typeof a.id === "string" && typeof a.accountId === "string" && typeof a.playbookId === "string" && ["In progress", "Retained", "Monitoring", "Churned"].includes(a.status) && typeof a.note === "string" && Number.isFinite(Date.parse(a.date)));
}

function App() {
  const [page, setPage] = useState("Overview");
  const [query, setQuery] = useState("");
  const [band, setBand] = useState("All accounts");
  const [plan, setPlan] = useState("All plans");
  const [industry, setIndustry] = useState("All industries");
  const [sort, setSort] = useState("risk");
  const [mobileNav, setMobileNav] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [notificationsRead, setNotificationsRead] = useState(false);
  const [dialog, setDialog] = useState(null);
  const [toast, setToast] = useState("");
  const [localActions, setLocalActionsState] = useState(() => readStorage("churn-actions-v1", [], validLocalActions));
  const [preferences, setPreferencesState] = useState(() => readStorage("churn-preferences-v1", defaultPreferences, (v) => v && typeof v.compact === "boolean" && typeof v.reminders === "boolean"));

  // Live data from the churn-scoring API.
  const [summary, setSummary] = useState([]);
  const [distribution, setDistribution] = useState([]);
  const [trend, setTrend] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [plays, setPlays] = useState([]);
  const [recentActions, setRecentActions] = useState([]);
  const [drift, setDrift] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [detail, setDetail] = useState(null);

  const searchRef = useRef(null);
  const toastTimer = useRef(null);
  const closeDialog = useCallback(() => setDialog(null), []);
  const notify = useCallback((message) => { clearTimeout(toastTimer.current); setToast(message); toastTimer.current = setTimeout(() => setToast(""), 4500); }, []);
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  useEffect(() => {
    Promise.all([
      api.getSummary(), api.getRiskDistribution(), api.getRiskTrend(), api.getAccounts(),
      api.getPlays(), api.getRecentActions(), api.getDrift(), api.getMeta(),
    ])
      .then(([summaryRes, distributionRes, trendRes, accountsRes, playsRes, actionsRes, driftRes, metaRes]) => {
        setSummary(summaryRes); setDistribution(distributionRes); setTrend(trendRes); setAccounts(accountsRes);
        setPlays(playsRes); setRecentActions(actionsRes); setDrift(driftRes); setMeta(metaRes);
      })
      .catch((err) => {
        console.error(err);
        setLoadError("Couldn't reach the churn-scoring API. Is churn-scoring/api.py running on :8000?");
      });
  }, []);

  const selectedAccount = dialog?.type === "account" ? dialog.id : null;
  useEffect(() => {
    if (!selectedAccount) { setDetail(null); return; }
    setDetail(null);
    api.getAccountDetail(selectedAccount).then((raw) => setDetail({ ...raw, color: accountColor(selectedAccount) })).catch((err) => { console.error(err); notify("Couldn't load that account's detail."); });
  }, [selectedAccount, notify]);

  useEffect(() => {
    const keydown = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); searchRef.current?.focus(); } if (e.key === "Escape") { setNotifications(false); setMobileNav(false); } };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, []);

  const saveLocally = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
  const setLocalActions = (next) => {
    const value = typeof next === "function" ? next(localActions) : next;
    setLocalActionsState(value);
    return saveLocally("churn-actions-v1", value);
  };
  const setPreferences = (value) => {
    setPreferencesState(value);
    if (!saveLocally("churn-preferences-v1", value)) notify("Browser storage unavailable. Preferences last for this session only.");
  };

  const resetFilters = () => { setQuery(""); setBand("All accounts"); setPlan("All plans"); setIndustry("All industries"); setSort("risk"); };
  const navigate = (destination) => { setPage(destination); setMobileNav(false); setNotifications(false); };
  const viewBand = (value) => { navigate("Accounts"); resetFilters(); setBand(value); };
  const showAccount = (id) => setDialog({ type: "account", id });
  const showLaunch = (playbookId) => setDialog({ type: "launch", playbookId });
  const launch = (accountId, playbookId) => {
    if (localActions.some((a) => a.accountId === accountId && a.playbookId === playbookId && a.status === "In progress")) { notify("This playbook is already in progress for this account."); return; }
    const saved = setLocalActions((previous) => [{ id: crypto.randomUUID(), accountId, playbookId, date: new Date().toISOString(), status: "In progress", note: "Playbook launched. Awaiting the first customer touchpoint." }, ...previous]);
    closeDialog(); notify(saved ? "Playbook launched. Track next steps in the activity log." : "Playbook launched for this session. Browser storage is unavailable.");
  };
  const exportAccounts = () => {
    const decorated = accounts.map((a) => ({ ...a, color: accountColor(a.id) }));
    const filtered = filterAccounts(decorated, { query, band, plan, industry, sort });
    const url = URL.createObjectURL(new Blob(["\uFEFF" + accountsCsv(filtered)], { type: "text/csv;charset=utf-8;" }));
    const link = document.createElement("a"); link.href = url; link.download = "churn-account-risk.csv"; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify(`Exported ${filtered.length} accounts.`);
  };

  const combinedActions = useMemo(() => {
    const local = localActions.map((a) => {
      const account = accounts.find((acc) => acc.id === a.accountId);
      const play = plays.find((p) => p.id === a.playbookId);
      return { id: a.id, accountId: a.accountId, account: account?.name ?? a.accountId, play: play?.title ?? a.playbookId, status: a.status, note: a.note, date: a.date, local: true };
    });
    const real = recentActions.map((a, i) => ({ id: `log-${i}`, accountId: a.accountId, account: a.account, play: a.play, status: a.status, note: a.action, date: a.date, local: false }));
    return [...local, ...real];
  }, [localActions, recentActions, accounts, plays]);

  const totalAccounts = accounts.length;
  const criticalAccount = accounts.find((a) => a.band === "Critical");
  const isPortfolio = page === "Overview" || page === "Accounts";
  const arrTotal = accounts.reduce((sum, a) => sum + (a.arr ?? 0), 0);
  const criticalTotal = accounts.filter((a) => a.band === "Critical").length;

  if (loadError) {
    return <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
      <p style={{ maxWidth: 420, textAlign: "center", color: "var(--muted)" }}>{loadError}</p>
    </div>;
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    {mobileNav && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <aside className={`sidebar sidebar-icons ${mobileNav ? "open" : ""}`} aria-label="Main navigation">
      <button className="brand" onClick={() => navigate("Overview")} aria-label="Signal home" title="Signal home"><span className="brand-mark"><Radio size={24} strokeWidth={2.5} /></span></button>
      <button className="workspace-switch" onClick={() => setDialog({ type: "workspace" })} aria-label="Churn early warning workspace" title="Churn early warning workspace"><span className="workspace-logo"><Layers size={18} /></span></button>
      <nav>{navItems.map(({ name, icon: Icon }) => <button key={name} className={`nav-item ${page === name ? "active" : ""}`} aria-label={name} title={name} aria-current={page === name ? "page" : undefined} onClick={() => navigate(name)}>
        <Icon size={20} strokeWidth={1.75} />
      </button>)}</nav>
      <div className="sidebar-bottom">
        <button className={`nav-item ${page === "Settings" ? "active" : ""}`} aria-label="Settings" title="Settings" aria-current={page === "Settings" ? "page" : undefined} onClick={() => navigate("Settings")}><Settings size={20} strokeWidth={1.75} /></button>
        <button className="nav-item" aria-label="Help & getting started" title="Help & getting started" onClick={() => setDialog({ type: "guide" })}><CircleHelp size={20} strokeWidth={1.75} /></button>
        <div className="user-profile"><button className="nav-item" aria-label="Profile and workspace" title="Profile and workspace" onClick={() => setDialog({ type: "workspace" })}><Fingerprint size={20} strokeWidth={1.75} /></button></div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={20} /></button><span className="breadcrumb-workspace">Workspace</span><ChevronRight size={13} /><strong>{page}</strong></div>
        <div className="topbar-actions">
          <div className="global-search"><Search size={17} /><input ref={searchRef} aria-label="Search accounts" placeholder="Search accounts…" value={query} onChange={(e) => { setQuery(e.target.value); if (!isPortfolio) navigate("Accounts"); }} /><kbd>Ctrl K</kbd></div>
          <span className="topbar-divider" />
          <div className="notification-wrap">
            <button className="icon-button notification-button" aria-label="Notifications" aria-expanded={notifications} onClick={() => setNotifications(!notifications)}><Bell size={19} />{!notificationsRead && <span />}</button>
            {notifications && <div className="notification-popover">
              <div className="popover-title"><h3>Notifications</h3><Badge tone="purple">Live</Badge></div>
              {criticalAccount && <button className="notification-item" onClick={() => { setNotificationsRead(true); setNotifications(false); showAccount(criticalAccount.id); }}><span className="notification-icon"><TrendingDown size={18} /></span><span><strong>{criticalAccount.name} needs attention</strong><small>Risk score {criticalAccount.score}, {criticalAccount.wow >= 0 ? "+" : ""}{criticalAccount.wow} pts this run.</small></span><ChevronRight size={15} /></button>}
              {drift?.nFeaturesAlerting > 0 && <div className="notification-item"><span className="notification-icon blue"><Activity size={18} /></span><span><strong>Feature drift detected</strong><small>{drift.nFeaturesAlerting} feature{drift.nFeaturesAlerting === 1 ? "" : "s"} exceeded the PSI threshold.</small></span></div>}
              <button className="text-button mark-read" onClick={() => { setNotificationsRead(true); setNotifications(false); notify("All notifications marked as read."); }}>Mark all as read</button>
            </div>}
          </div>
          <button className="avatar top-avatar" aria-label="Open profile" onClick={() => setDialog({ type: "workspace" })}>CS</button>
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <div className="page-heading">
          <div><div className="eyebrow"><span />CUSTOMER INTELLIGENCE</div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div>
          <div className="heading-actions">
            {isPortfolio && <button className="button" onClick={exportAccounts}><Download size={15} />Export report</button>}
            {page === "Activity log" && plays.length > 0 && <button className="button primary" onClick={() => showLaunch(plays[0].id)}><Plus size={16} />Launch a playbook</button>}
          </div>
        </div>
        {page === "Overview" && (summary.length ? <DashboardCharts summary={summary} distribution={distribution} trend={trend} totalAccounts={totalAccounts} viewRisk={() => viewBand("Critical")} viewBand={viewBand} /> : <Spinner label="Loading portfolio metrics…" />)}
        {page === "Accounts" && <div className="portfolio-strip"><Users size={20} /><span><strong>{totalAccounts}</strong> accounts monitored</span><span><strong>{money(arrTotal)}</strong> portfolio ARR</span><span><strong>{criticalTotal}</strong> need your attention</span><Badge tone="purple">Live portfolio</Badge></div>}
        {page === "Accounts" && (accounts.length ? <AccountsTable page={page} accounts={accounts} query={query} setQuery={setQuery} band={band} setBand={setBand} plan={plan} setPlan={setPlan} industry={industry} setIndustry={setIndustry} sort={sort} setSort={setSort} compact={preferences.compact} onSelect={showAccount} onGuide={() => setDialog({ type: "guide" })} /> : <Spinner label="Loading accounts…" />)}
        {page === "Overview" && plays.length > 0 && <DashboardBottom navigate={navigate} onLaunch={showLaunch} plays={plays} driftCount={drift?.nFeaturesAlerting ?? 0} />}
        {page === "Playbooks" && (plays.length ? <Playbooks plays={plays} onLaunch={showLaunch} /> : <Spinner label="Loading playbooks…" />)}
        {page === "Evaluation" && <Evaluation />}
        {page === "Activity log" && <ActivityLog actions={combinedActions} onSelect={showAccount} onOutcome={(action) => setDialog({ type: "outcome", action })} />}
        {page === "Settings" && <div className="settings-layout">
          <section className="panel settings-card"><SectionHeader title="Personal preferences" description="These settings apply to this browser only." />
            <div className="setting-row"><div><h3>Compact account rows</h3><p>Fit more of your portfolio into a single view.</p></div><button role="switch" aria-checked={preferences.compact} aria-label="Compact account rows" className={`toggle ${preferences.compact ? "on" : ""}`} onClick={() => setPreferences({ ...preferences, compact: !preferences.compact })}><span /></button></div>
            <div className="setting-row"><div><h3>Renewal reminders</h3><p>Highlight renewals within 30 days in account details.</p></div><button role="switch" aria-checked={preferences.reminders} aria-label="Renewal reminders" className={`toggle ${preferences.reminders ? "on" : ""}`} onClick={() => setPreferences({ ...preferences, reminders: !preferences.reminders })}><span /></button></div>
            <div className="settings-info"><Check size={15} />Preferences save automatically.</div>
          </section>
          <section className="panel settings-card"><SectionHeader title="Session activity" description="Playbooks you launch are stored in this browser only." />
            <div className="setting-row"><div><h3>Reset session activity</h3><p>Clear locally-launched playbooks. The live outcomes log is unaffected.</p></div><button className="button danger-button" onClick={() => setDialog({ type: "reset" })}>Reset session</button></div>
            <div className="setting-row"><div><h3>What's next?</h3><p>See what's connected live vs. still session-only.</p></div><button className="text-button" onClick={() => setDialog({ type: "roadmap" })}>View implementation notes <ArrowUpRight size={15} /></button></div>
          </section>
        </div>}
        <footer className="page-footer"><span><Radio size={13} />A little signal. A lot of clarity.</span><div><span className="demo-pill">LIVE</span><span>Snapshot · {meta?.asOf ?? "loading…"}</span></div></footer>
      </main>
    </div>

    {selectedAccount && <Modal title="Account intelligence" onClose={closeDialog} drawer><AccountDetail id={selectedAccount} detail={detail} reminders={preferences.reminders} localActions={localActions} onLaunch={(accId) => launch(accId, detail?.play?.key)} /></Modal>}
    {dialog?.type === "launch" && <Modal title="Launch a playbook" onClose={closeDialog}><LaunchForm playbook={plays.find((p) => p.id === dialog.playbookId)} accounts={accounts} onLaunch={launch} /></Modal>}
    {dialog?.type === "outcome" && <Modal title="Capture the outcome" onClose={closeDialog}><OutcomeForm action={dialog.action} onSave={(status, note) => { if (dialog.action.local) { const saved = setLocalActions(localActions.map((a) => a.id === dialog.action.id ? { ...a, status, note } : a)); closeDialog(); notify(saved ? "Outcome recorded for this session." : "Outcome recorded for this session. Browser storage is unavailable."); } else { closeDialog(); notify("This action comes from the live log — outcome editing isn't wired to the outcomes service yet."); } }} /></Modal>}
    {dialog?.type === "reset" && <Modal title="Reset session activity?" onClose={closeDialog}><div className="modal-content"><p>This removes playbooks you launched in this browser this session. The live actions log and preferences are not affected. This cannot be undone.</p><div className="modal-actions"><button className="button" onClick={closeDialog}>Cancel</button><button className="button primary" onClick={() => { setLocalActions([]); closeDialog(); notify("Session activity cleared."); }}>Reset session</button></div></div></Modal>}
    {dialog?.type === "workspace" && <Modal title="Your workspace" onClose={closeDialog}><div className="modal-content workspace-details"><span className="workspace-logo"><Layers size={25} /></span><h3>Churn early warning</h3><Badge tone="purple">Connected to churn-scoring API</Badge><p>This workspace is reading live account scores, signals, and playbooks from the churn-scoring service (model {meta?.modelVersion ?? "…"}). Authentication and team management aren't wired up yet.</p><button className="button" onClick={() => { closeDialog(); navigate("Settings"); }}><Settings size={15} />Workspace preferences</button></div></Modal>}
    {dialog?.type === "guide" && <Modal title="A clearer picture, before the renewal" onClose={closeDialog}><div className="modal-content guide-content"><div className="guide-hero"><Fingerprint size={31} /><span>Understand the why.<br /><strong>Choose your next step.</strong></span></div><p>Signal brings usage decay, feature abandonment, and support friction into one account view, scored live by the churn-scoring model.</p><h3>How to read a risk band</h3><div className="risk-guide"><RiskBadge band="Critical" /><span>Prioritize a personal check-in this week.</span><RiskBadge band="High" /><span>Investigate the top signal soon.</span><RiskBadge band="Medium" /><span>Monitor closely, no urgent action yet.</span><RiskBadge band="Low" /><span>Maintain healthy engagement.</span></div><h3>Try the workflow</h3><StepList steps={["Search or filter accounts, then open an account.", "Review contributing signals and launch a playbook.", "Record the outcome in the activity log."]} /><p className="notice">Scores, signals, and monitoring metrics are live from the scoring/policy/monitoring services. Playbook launches and outcomes stay local to this browser until a write-back endpoint exists.</p></div></Modal>}
    {dialog?.type === "roadmap" && <Modal title="From prototype to production" onClose={closeDialog}><div className="modal-content"><Badge tone="success">Connected · most phases live</Badge><p className="roadmap-intro">This workspace now reads from the real churn-scoring services rather than fixture data.</p><StepList steps={["UI foundation — responsive dashboards and workflows. Done.", "Telemetry + features — churn-pipeline computes and versions features. Done.", "Risk scoring + API — churn-scoring serves live scores and attribution. Done.", "Policy — churn-policy maps scores to recommended plays. Done.", "Evaluation — churn-outcomes tracks ranking quality and play effectiveness. Done.", "Monitoring — churn-monitoring tracks feature drift (PSI). Done.", "Remaining: write playbook launches/outcomes back to the outcomes log, and automate CI release gates with canary rollout + rollback."]} /></div></Modal>}
    <Toast message={toast} />
  </div>;
}

export default App;
