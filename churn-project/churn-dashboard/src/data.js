// Small, backend-agnostic helpers shared by the dashboard views. Unlike the
// original UI reference this is based on, there is no local fixture data
// here — every account, score, signal, and metric comes from the
// churn-scoring API (see lib/api.js). These are just formatting/filtering
// utilities that operate on whatever the API returns.

export const BAND_TONE = { Critical: "danger", High: "warning", Medium: "purple", Low: "success" };
export const BAND_ORDER = ["Critical", "High", "Medium", "Low"];
const PALETTE = ["violet", "blue", "orange", "green", "pink", "indigo"];

export function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0, notation: "compact" }).format(value);
}

// A stable, cosmetic-only color per account, derived from its id so the
// same account always gets the same avatar color. There is no "color"
// field in the churn-scoring API — this is presentation, not data.
export function accountColor(id) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function filterAccounts(items, { query = "", band = "All accounts", plan = "All plans", industry = "All industries", sort = "risk" } = {}) {
  const search = query.trim().toLowerCase();
  return items
    .filter((a) =>
      (!search || `${a.name} ${a.industry} ${a.signal}`.toLowerCase().includes(search)) &&
      (band === "All accounts" || a.band === band) &&
      (plan === "All plans" || a.plan === plan) &&
      (industry === "All industries" || a.industry === industry)
    )
    .sort((a, b) => (sort === "arr" ? b.arr - a.arr : sort === "renewal" ? (a.renewalDays ?? Infinity) - (b.renewalDays ?? Infinity) : b.score - a.score));
}

export function initialsFromName(name) {
  const parts = (name ?? "").split(" ").filter(Boolean);
  return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

// Two status vocabularies exist: the real actions_log.csv values (Pending,
// In progress, Completed) and the ones a locally-launched playbook can be
// set to in the outcome form (In progress, Monitoring, Retained, Churned).
export function actionStatusTone(status) {
  if (status === "Completed" || status === "Retained") return "success";
  if (status === "In progress" || status === "Monitoring") return "warning";
  if (status === "Churned") return "danger";
  return "purple";
}

export function accountsCsv(items) {
  const escape = (value) => `"${String(value).replace(/^[=+\-@]/, "'$&").replaceAll('"', '""')}"`;
  return [
    ["Account", "Risk score", "Risk band", "ARR (USD)", "Usage change (%)", "Signal", "Industry", "Plan", "Renewal"],
    ...items.map((a) => [a.name, a.score, a.band, a.arr, a.usage, a.signal, a.industry, a.plan, a.renewal]),
  ].map((row) => row.map(escape).join(",")).join("\r\n");
}
