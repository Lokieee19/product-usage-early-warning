const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const getSummary = () => get("/api/summary");
export const getRiskDistribution = () => get("/api/risk-distribution");
export const getRiskTrend = () => get("/api/risk-trend");
export const getAccounts = () => get("/api/accounts");
export const getAccountDetail = (accountId) => get(`/api/accounts/${accountId}`);
export const getRecentActions = (limit = 20) => get(`/api/recent-actions?limit=${limit}`);
export const getModelPerformance = () => get("/api/model-performance");
export const getPlays = () => get("/api/plays");
export const getDrift = () => get("/api/drift");
export const getMeta = () => get("/api/meta");
