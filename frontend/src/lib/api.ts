const API_BASE = "/api";

type FetchOptions = RequestInit & { token?: string };

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { token, ...fetchOpts } = opts;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOpts.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...fetchOpts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export const auth = {
  signup: (data: { email: string; password: string; full_name?: string; workspace_name: string }) =>
    apiFetch<{ access_token: string; user_id: string; default_workspace_id: string }>("/auth/signup", {
      method: "POST", body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    apiFetch<{ access_token: string; user_id: string; default_workspace_id: string }>("/auth/login", {
      method: "POST", body: JSON.stringify(data),
    }),
  me: (token: string) => apiFetch<any>("/auth/me", { token }),
};

// Offers
export const offers = {
  list: (token: string, accountId: string) =>
    apiFetch<any[]>("/offers", { token, headers: { "X-Account-Id": accountId } }),
  create: (token: string, accountId: string, data: any) =>
    apiFetch<any>("/offers", { method: "POST", token, body: JSON.stringify(data), headers: { "X-Account-Id": accountId } }),
};

// Performance
export const performance = {
  ingestSnapshots: (token: string, accountId: string, data: any) =>
    apiFetch<any>("/performance/snapshots", { method: "POST", token, body: JSON.stringify(data), headers: { "X-Account-Id": accountId } }),
  getHistory: (token: string, accountId: string, adId: string) =>
    apiFetch<any[]>(`/performance/snapshots/${adId}`, { token, headers: { "X-Account-Id": accountId } }),
  getQuestions: (token: string, accountId: string) =>
    apiFetch<any[]>("/performance/questions", { token, headers: { "X-Account-Id": accountId } }),
  answerQuestion: (token: string, accountId: string, questionId: string, data: any) =>
    apiFetch<any>(`/performance/questions/${questionId}/answer`, { method: "POST", token, body: JSON.stringify(data), headers: { "X-Account-Id": accountId } }),
  getWinningDef: (token: string, accountId: string) =>
    apiFetch<any>("/performance/winning-definition", { token, headers: { "X-Account-Id": accountId } }),
  getBenchmarks: (industry: string) =>
    apiFetch<any>(`/performance/benchmarks/${industry}`),
  syncLearning: (token: string, accountId: string) =>
    apiFetch<any>("/performance/sync-learning", { method: "POST", token, headers: { "X-Account-Id": accountId } }),
};

// Creative library
export const creativeLibrary = {
  search: (token: string, accountId: string, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch<any[]>(`/creative-library/assets?${qs}`, { token, headers: { "X-Account-Id": accountId } });
  },
  searchSwipes: (token: string, accountId: string, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch<any[]>(`/creative-library/swipes?${qs}`, { token, headers: { "X-Account-Id": accountId } });
  },
  findSimilar: (token: string, accountId: string, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch<any[]>(`/creative-library/similar?${qs}`, { token, headers: { "X-Account-Id": accountId } });
  },
  ingest: (token: string, accountId: string, data: any) =>
    apiFetch<any>("/creative-library/ingest", { method: "POST", token, body: JSON.stringify(data), headers: { "X-Account-Id": accountId } }),
  categories: () => apiFetch<any>("/creative-library/categories"),
};

// Knowledge
export const knowledge = {
  exportMarkdown: (token: string, accountId: string) =>
    apiFetch<any>("/knowledge/export/markdown", { token, headers: { "X-Account-Id": accountId } }),
  exportPairs: (token: string, accountId: string) =>
    apiFetch<any>("/knowledge/export/training-pairs", { token, headers: { "X-Account-Id": accountId } }),
};

// Seeds
export const seeds = {
  list: (token: string, accountId: string, offerId: string) =>
    apiFetch<any[]>(`/seeds/${offerId}`, { token, headers: { "X-Account-Id": accountId } }),
  submit: (token: string, accountId: string, offerId: string, data: any) =>
    apiFetch<any>(`/seeds/${offerId}`, { method: "POST", token, body: JSON.stringify(data), headers: { "X-Account-Id": accountId } }),
};
